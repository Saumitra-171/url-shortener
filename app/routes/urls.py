from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import get_db
from app.core.deps import get_current_user
from app.models.schemas import (
    AnalyticsResponse,
    ClickDetail,
    ShortenRequest,
    ShortenResponse,
    URLStats,
)
from app.models.user import User
from app.services import url_service

from app.core.rate_limit import limit_by_user

router = APIRouter()


@router.post("/shorten", response_model=ShortenResponse, status_code=201, dependencies=[Depends(limit_by_user("shorten", 10, 60))],)
def shorten_url(
    payload: ShortenRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    url = url_service.create_short_url(db, payload.url, current_user.id)
    return ShortenResponse(
        short_code=url.short_code,
        short_url=f"{settings.base_url}/{url.short_code}",
        original_url=url.original_url,
        created_at=url.created_at,
    )


@router.get("/{short_code}/analytics", response_model=AnalyticsResponse)
def get_analytics(
    short_code: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = url_service.get_analytics(db, short_code, current_user.id)
    if not result:
        raise HTTPException(status_code=404, detail="Short URL not found.")
    url, clicks = result
    return AnalyticsResponse(
        stats=URLStats.model_validate(url),
        recent_clicks=[ClickDetail.model_validate(c) for c in clicks],
    )


@router.delete("/{short_code}", status_code=204)
def delete_url(
    short_code: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if not url_service.delete_url(db, short_code, current_user.id):
        raise HTTPException(status_code=404, detail="Short URL not found.")


@router.get("/{short_code}")  # intentionally public: anyone with the link can follow it
def redirect(short_code: str, request: Request, db: Session = Depends(get_db)):
    target = url_service.resolve_url(db, short_code)
    if not target:
        raise HTTPException(status_code=404, detail="Short URL not found.")
    url_id, original_url = target

    referrer = request.headers.get("referer")
    user_agent = request.headers.get("user-agent")
    ip = request.client.host if request.client else None
    url_service.record_click(db, url_id, referrer, user_agent, ip)

    return RedirectResponse(url=original_url, status_code=302)