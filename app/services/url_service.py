import random
import string
from datetime import datetime, timezone

from sqlalchemy.orm import Session
from sqlalchemy import select, update

from app.core.config import settings
from app.core.cache import cache_get, cache_set, cache_delete
from app.models.url import URL
from app.models.click import Click


ALPHABET = string.ascii_letters + string.digits


def _generate_code(length: int = 6) -> str:
    return "".join(random.choices(ALPHABET, k=length))


def create_short_url(db: Session, original_url: str) -> URL:
    for _ in range(5):
        code = _generate_code()
        exists = db.scalar(select(URL).where(URL.short_code == code))
        if not exists:
            break
    else:
        raise RuntimeError("Failed to generate unique short code — please retry.")

    url = URL(short_code=code, original_url=original_url)
    db.add(url)
    db.commit()
    db.refresh(url)

    # Warm the cache immediately after creation
    cache_set(f"url:{code}", original_url)
    return url


def resolve_url(db: Session, short_code: str) -> URL | None:
    # Check Redis first
    cached = cache_get(f"url:{short_code}")
    if cached:
        # Still need the DB row to record the click
        return db.scalar(select(URL).where(URL.short_code == short_code))

    # Cache miss — go to Postgres
    url = db.scalar(select(URL).where(URL.short_code == short_code))
    if url:
        cache_set(f"url:{short_code}", url.original_url)
    return url


def record_click(db: Session, url: URL, referrer: str | None, user_agent: str | None, ip_address: str | None):
    now = datetime.now(timezone.utc)
    db.execute(
        update(URL)
        .where(URL.id == url.id)
        .values(click_count=URL.click_count + 1, last_clicked_at=now)
    )
    click = Click(url_id=url.id, referrer=referrer, user_agent=user_agent, ip_address=ip_address)
    db.add(click)
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