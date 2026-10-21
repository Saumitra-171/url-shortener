import json
import secrets
import string
from datetime import datetime, time, timedelta, timezone

from sqlalchemy import and_, func, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.cache import CACHE_TTL, cache_delete, cache_get, cache_set
from app.core.constants import RESERVED_CODES
from app.models.click import Click
from app.models.url import URL
from app.core.useragent import classify_browser

from collections import Counter


ALPHABET = string.ascii_letters + string.digits


class AliasTakenError(Exception):
    pass


class LinkExpired(Exception):
    pass


def _now() -> datetime:
    return datetime.now(timezone.utc)  # a function so tests can move the clock


def _as_utc(dt: datetime | None) -> datetime | None:
    # Postgres returns timezone-aware datetimes, but SQLite (used in tests) returns naive ones.
    # Comparing the two raises TypeError, so normalise before comparing.
    if dt is not None and dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt


def _generate_code(length: int = 6) -> str:
    return "".join(secrets.choice(ALPHABET) for _ in range(length))


def _cache_payload(url: URL) -> str:
    exp = _as_utc(url.expires_at)
    return json.dumps({
        "id": url.id,
        "url": url.original_url,
        "exp": exp.timestamp() if exp else None,
    })


def _cache_url(url: URL) -> None:
    ttl = CACHE_TTL
    exp = _as_utc(url.expires_at)
    if exp is not None:
        remaining = int((exp - _now()).total_seconds())
        if remaining <= 0:
            return  # already expired: don't cache it at all
        ttl = min(CACHE_TTL, remaining)  # Redis evicts the entry no later than the expiry
    cache_set(f"url:{url.short_code}", _cache_payload(url), ttl)


def _try_insert(db: Session, code: str, original_url: str, owner_id: int,
                expires_at: datetime | None) -> URL | None:
    url = URL(short_code=code, original_url=original_url, owner_id=owner_id, expires_at=expires_at)
    db.add(url)
    try:
        db.commit()
    except IntegrityError:  # the unique constraint is the real guard against duplicates
        db.rollback()
        return None
    db.refresh(url)
    return url


def create_short_url(db: Session, original_url: str, owner_id: int,
                     alias: str | None = None, expires_at: datetime | None = None) -> URL:
    if alias is not None:
        url = _try_insert(db, alias, original_url, owner_id, expires_at)
        if url is None:
            raise AliasTakenError(alias)
        _cache_url(url)
        return url

    for _ in range(5):
        code = _generate_code()
        if code.lower() in RESERVED_CODES:
            continue
        url = _try_insert(db, code, original_url, owner_id, expires_at)
        if url is not None:
            _cache_url(url)
            return url
    raise RuntimeError("Could not generate a unique short code, please retry.")


def resolve_url(db: Session, short_code: str) -> tuple[int, str] | None:
    """Return (url_id, original_url), None if unknown, or raise LinkExpired."""
    cached = cache_get(f"url:{short_code}")
    if cached:
        data = json.loads(cached)
        # .get() because entries cached before expiry existed have no "exp" key
        if data.get("exp") is not None and data["exp"] <= _now().timestamp():
            raise LinkExpired(short_code)
        return data["id"], data["url"]

    url = db.scalar(select(URL).where(URL.short_code == short_code))
    if not url:
        return None
    exp = _as_utc(url.expires_at)
    if exp is not None and exp <= _now():
        raise LinkExpired(short_code)
    _cache_url(url)
    return url.id, url.original_url


def record_click(
    db: Session,
    url_id: int,
    referrer: str | None,
    user_agent: str | None,
    ip_address: str | None,
):
    now = datetime.now(timezone.utc)
    db.execute(
        update(URL)
        .where(URL.id == url_id)
        .values(click_count=URL.click_count + 1, last_clicked_at=now)
    )
    db.add(Click(url_id=url_id, referrer=referrer, user_agent=user_agent, ip_address=ip_address))
    db.commit()


def get_analytics(db: Session, short_code: str, owner_id: int) -> tuple[URL, list[Click]] | None:
    url = db.scalar(select(URL).where(URL.short_code == short_code, URL.owner_id == owner_id))
    if not url:
        return None
    recent_clicks = db.scalars(
        select(Click).where(Click.url_id == url.id).order_by(Click.clicked_at.desc()).limit(20)
    ).all()
    return url, list(recent_clicks)


def delete_url(db: Session, short_code: str, owner_id: int) -> bool:
    url = db.scalar(select(URL).where(URL.short_code == short_code, URL.owner_id == owner_id))
    if not url:
        return False
    db.delete(url)
    db.commit()
    cache_delete(f"url:{short_code}")
    return True

def get_summary(db: Session, short_code: str, owner_id: int, days: int) -> dict | None:
    url = db.scalar(select(URL).where(URL.short_code == short_code, URL.owner_id == owner_id))
    if not url:
        return None

    first_day = _now().date() - timedelta(days=days - 1)
    since = datetime.combine(first_day, time.min, tzinfo=timezone.utc)
    in_window = and_(Click.url_id == url.id, Click.clicked_at >= since)

    # Clicks per day. GROUP BY runs in the database, so at most `days` rows come back.
    day = func.date(Click.clicked_at)
    counts = {str(d): n for d, n in db.execute(select(day, func.count()).where(in_window).group_by(day))}
    per_day = []
    for i in range(days):  # fill the gaps: a day with no clicks must appear as 0
        d = (first_day + timedelta(days=i)).isoformat()
        per_day.append({"date": d, "clicks": counts.get(d, 0)})

    # Top referrers, with "(direct)" standing in for clicks that had none.
    referrer = func.coalesce(Click.referrer, "(direct)")
    referrer_rows = db.execute(
        select(referrer, func.count())
        .where(in_window)
        .group_by(referrer)
        .order_by(func.count().desc(), referrer)
        .limit(5)
    ).all()

    # Browsers: group by DISTINCT user agent in SQL, then classify each in Python.
    browsers: Counter[str] = Counter()
    for user_agent, n in db.execute(select(Click.user_agent, func.count()).where(in_window).group_by(Click.user_agent)):
        browsers[classify_browser(user_agent)] += n

    return {
        "short_code": url.short_code,
        "days": days,
        "total_clicks": sum(d["clicks"] for d in per_day),
        "clicks_per_day": per_day,
        "top_referrers": [{"referrer": r, "clicks": n} for r, n in referrer_rows],
        "browsers": [{"browser": b, "clicks": n} for b, n in browsers.most_common()],
    }

def list_urls(db: Session, owner_id: int, limit: int, offset: int) -> list[URL]:
    return list(db.scalars(
        select(URL)
        .where(URL.owner_id == owner_id)
        # id is the tie-breaker: several links can share a created_at timestamp
        .order_by(URL.created_at.desc(), URL.id.desc())
        .limit(limit)
        .offset(offset)
    ))