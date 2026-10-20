from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.core.config import settings
from app.routes.auth import router as auth_router
from app.routes.urls import router as url_router
from app.services.click_worker import ClickWorker
from app.core.cache import redis_client
from app.core.database import SessionLocal, get_db

import redis as redis_lib
from fastapi import Depends, HTTPException
from sqlalchemy import text
from sqlalchemy.orm import Session


@asynccontextmanager
async def lifespan(app: FastAPI):
    worker = None
    if settings.run_click_worker:
        worker = ClickWorker(SessionLocal)
        worker.start()
    yield  # the app serves requests here
    if worker:
        worker.stop()  # finishes the current batch and drains the queue


app = FastAPI(
    title=settings.app_name,
    description="A URL shortener with click analytics.",
    version="1.0.0",
    lifespan=lifespan,
)

@app.get("/health")
def health():
    return {"status": "ok", "service": settings.app_name}

@app.get("/health/ready")
def ready(db: Session = Depends(get_db)):
    try:
        db.execute(text("select 1"))
    except Exception:
        raise HTTPException(status_code=503, detail="Database unavailable.")
    try:
        redis_client.ping()
        cache = "up"
    except redis_lib.RedisError:
        cache = "down"  # the app still works without Redis, only slower
    return {
        "status": "ok" if cache == "up" else "degraded",
        "database": "up",
        "redis": cache,
    }


app.include_router(auth_router)
app.include_router(url_router, tags=["URLs"])