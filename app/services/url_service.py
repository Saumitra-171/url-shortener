import json
import secrets
import string
from datetime import datetime, timezone

from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.cache import cache_get, cache_set, cache_delete
from app.models.click import Click
from app.models.url import URL

ALPHABET = string.ascii_letters + string.digits


def _generate_code(length: int = 6) -> str:
    return "".join(secrets.choice(ALPHABET) for _ in range(length))


def _cache_payload(url: URL) -> str:
    return json.dumps({"id": url.id, "url": url.original_url})


def create_short_url(db: Session, original_url: str) -> URL:
    for _ in range(5):
        url = URL(short_code=_generate_code(), original_url=original_url)
        db.add(url)
        try:
            db.commit()
        except IntegrityError:
            db.rollback()  # required: the session is unusable after a failed commit
            continue
        db.refresh(url)
        cache_set(f"url:{url.short_code}", _cache_payload(url))
        return url
    raise RuntimeError("Could not generate a unique short code, please retry.")


def resolve_url(db: Session, short_code: str) -> tuple[int, str] | None:
    """Return (url_id, original_url) or None. Hits Redis first."""
    cached = cache_get(f"url:{short_code}")
    if cached:
        data = json.loads(cached)
        return data["id"], data["url"]

    url = db.scalar(select(URL).where(URL.short_code == short_code))
    if not url:
        return None
    cache_set(f"url:{short_code}", _cache_payload(url))
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

def get_analytics(db: Session, short_code: str) -> tuple[URL, list[Click]] | None:
    url = db.scalar(select(URL).where(URL.short_code == short_code))
    if not url:
        return None
    recent_clicks = db.scalars(
        select(Click).where(Click.url_id == url.id).order_by(Click.clicked_at.desc()).limit(20)
    ).all()
    return url, list(recent_clicks)


def delete_url(db: Session, short_code: str) -> bool:
    url = db.scalar(select(URL).where(URL.short_code == short_code))
    if not url:
        return False
    db.delete(url)
    db.commit()
    # Invalidate cache on delete
    cache_delete(f"url:{short_code}")
    return True