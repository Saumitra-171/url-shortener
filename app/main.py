from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.core.config import settings
from app.core.database import SessionLocal
from app.routes.auth import router as auth_router
from app.routes.urls import router as url_router
from app.services.click_worker import ClickWorker


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


app.include_router(auth_router)
app.include_router(url_router, tags=["URLs"])