from fastapi import APIRouter, Depends, HTTPException, Query, Request
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
    SummaryResponse,
    URLStats,
)
from app.models.user import User
from app.services import click_worker, url_service

from app.core.rate_limit import limit_by_user

router = APIRouter()


@router.post(
    "/shorten",
    response_model=ShortenResponse,
    status_code=201,
    dependencies=[Depends(limit_by_user("shorten", 10, 60))],
)
def shorten_url(
    payload: ShortenRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        url = url_service.create_short_url(
            db, payload.url, current_user.id, alias=payload.alias, expires_at=payload.expires_at
        )
    except url_service.AliasTakenError:
        raise HTTPException(status_code=409, detail="Alias already taken.")
    return ShortenResponse(
        short_code=url.short_code,
        short_url=f"{settings.base_url}/{url.short_code}",
        original_url=url.original_url,
        created_at=url.created_at,
        expires_at=url.expires_at,
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

@router.get("/{short_code}/analytics/summary", response_model=SummaryResponse)
def get_analytics_summary(
    short_code: str,
    days: int = Query(30, ge=1, le=90),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = url_service.get_summary(db, short_code, current_user.id, days)
    if not result:
        raise HTTPException(status_code=404, detail="Short URL not found.")
    return result

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
    try:
        target = url_service.resolve_url(db, short_code)
    except url_service.LinkExpired:
        raise HTTPException(status_code=410, detail="This link has expired.")
    if not target:
        raise HTTPException(status_code=404, detail="Short URL not found.")
    url_id, original_url = target

    referrer = request.headers.get("referer")
    user_agent = request.headers.get("user-agent")
    ip = request.client.host if request.client else None
    if not click_worker.enqueue_click(url_id, referrer, user_agent, ip):
    # Redis is down: fall back to the old synchronous write so the click is not lost.
        url_service.record_click(db, url_id, referrer, user_agent, ip)

    return RedirectResponse(url=original_url, status_code=302)