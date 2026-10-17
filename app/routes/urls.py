from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.config import settings
from app.models.schemas import (
    ShortenRequest,
    ShortenResponse,
    AnalyticsResponse,
    URLStats,
    ClickDetail,
)
from app.services import url_service

router = APIRouter()


@router.post("/shorten", response_model=ShortenResponse, status_code=201)
def shorten_url(payload: ShortenRequest, db: Session = Depends(get_db)):
    url = url_service.create_short_url(db, payload.url)
    return ShortenResponse(
        short_code=url.short_code,
        short_url=f"{settings.base_url}/{url.short_code}",
        original_url=url.original_url,
        created_at=url.created_at,
    )


@router.get("/{short_code}/analytics", response_model=AnalyticsResponse)
def get_analytics(short_code: str, db: Session = Depends(get_db)):
    result = url_service.get_analytics(db, short_code)
    if not result:
        raise HTTPException(status_code=404, detail="Short URL not found.")
    url, clicks = result
    return AnalyticsResponse(
        stats=URLStats.model_validate(url),
        recent_clicks=[ClickDetail.model_validate(c) for c in clicks],
    )


@router.delete("/{short_code}", status_code=204)
def delete_url(short_code: str, db: Session = Depends(get_db)):
    deleted = url_service.delete_url(db, short_code)
    if not deleted:
        raise HTTPException(status_code=404, detail="Short URL not found.")


@router.get("/{short_code}")
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