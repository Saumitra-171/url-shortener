from fastapi import FastAPI
from app.core.config import settings
from app.routes.urls import router as url_router

app = FastAPI(
    title=settings.app_name,
    description="A URL shortener with click analytics.",
    version="1.0.0",
)


@app.get("/health")
def health():
    return {"status": "ok", "service": settings.app_name}


app.include_router(url_router, tags=["URLs"])