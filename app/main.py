from contextlib import asynccontextmanager
from pathlib import Path

import redis as redis_lib
from fastapi import Depends, FastAPI, HTTPException
from fastapi.responses import FileResponse, RedirectResponse
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.cache import redis_client
from app.core.config import settings
from app.core.database import SessionLocal, get_db
from app.routes.auth import router as auth_router
from app.routes.urls import router as url_router
from app.services.click_worker import ClickWorker

# Where `npm run build` puts the React app (see outDir in frontend/vite.config.js).
FRONTEND_DIR = Path(__file__).parent / "static" / "app"
IMMUTABLE = {"Cache-Control": "public, max-age=31536000, immutable"}  # hashed filenames never change
NO_CACHE = {"Cache-Control": "no-cache"}  # always revalidate, so a new deploy is picked up


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


@app.get("/health", tags=["Health"])
def health():
    return {"status": "ok", "service": settings.app_name}


@app.get("/health/ready", tags=["Health"])
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


# ---------- the web app ----------
# These routes are declared BEFORE the routers, so /app/... can never be mistaken for a short code.
# ("app" is also in RESERVED_CODES, so nobody can create a link with that name.)

@app.get("/", include_in_schema=False)
def root():
    built = (FRONTEND_DIR / "index.html").is_file()
    return RedirectResponse("/app/" if built else "/docs", status_code=302)


@app.get("/app", include_in_schema=False)
def app_without_slash():
    return RedirectResponse("/app/", status_code=302)


@app.get("/app/{path:path}", include_in_schema=False)
def frontend(path: str):
    index = FRONTEND_DIR / "index.html"
    if not index.is_file():
        raise HTTPException(status_code=404, detail="The web app has not been built.")
    try:
        base = FRONTEND_DIR.resolve()
        candidate = (FRONTEND_DIR / path).resolve()  # resolves any ".." in the requested path
        # Only serve a real file that is INSIDE the build folder.
        if path and candidate.is_file() and base in candidate.parents:
            return FileResponse(candidate, headers=IMMUTABLE if path.startswith("assets/") else NO_CACHE)
    except (ValueError, OSError):
        pass  # a malformed path: treat it like any other unknown route
    return FileResponse(index, headers=NO_CACHE)  # client-side routes land here


app.include_router(auth_router)
app.include_router(url_router, tags=["URLs"])