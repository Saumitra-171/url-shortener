import os

# Set BEFORE the app is imported. Direct assignment (not setdefault) guarantees tests
# can never touch your real Postgres or Redis, even if .env points at them.
os.environ["DATABASE_URL"] = "sqlite://"
os.environ["REDIS_URL"] = "redis://localhost:6379/15"
os.environ["SECRET_KEY"] = "test-secret-key-not-for-production"

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core import security
from app.core.database import Base, get_db
from app.main import app
from app.models import click, url, user  # noqa: F401  (registers models on Base.metadata)
from app.services import url_service

import fakeredis

from app.core import rate_limit


@pytest.fixture()
def session_factory():
    # In-memory SQLite. StaticPool keeps ONE connection alive, otherwise every
    # new connection would get its own empty database.
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    @event.listens_for(engine, "connect")
    def enable_foreign_keys(dbapi_conn, _record):
        # SQLite ignores foreign keys (and ON DELETE CASCADE) unless asked.
        dbapi_conn.execute("PRAGMA foreign_keys=ON")

    Base.metadata.create_all(engine)
    yield sessionmaker(bind=engine, autoflush=False, autocommit=False)
    engine.dispose()


@pytest.fixture(autouse=True)
def fake_cache(monkeypatch):
    store: dict[str, str] = {}
    # Patch the names inside url_service, because it imported them with
    # `from app.core.cache import ...`, which copied them into its own namespace.
    monkeypatch.setattr(url_service, "cache_get", lambda key: store.get(key))
    monkeypatch.setattr(url_service, "cache_set", lambda key, value, ttl=3600: store.__setitem__(key, value))
    monkeypatch.setattr(url_service, "cache_delete", lambda key: store.pop(key, None))
    return store


@pytest.fixture(autouse=True)
def fast_hashing(monkeypatch):
    # bcrypt is slow on purpose. Minimum cost keeps the suite fast.
    monkeypatch.setattr(security, "BCRYPT_ROUNDS", 4)


@pytest.fixture()
def client(session_factory):
    def override_get_db():
        db = session_factory()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


def register_and_login(client, email, password="password123"):
    client.post("/auth/register", json={"email": email, "password": password})
    response = client.post("/auth/login", data={"username": email, "password": password})
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


@pytest.fixture()
def auth_headers(client):
    return register_and_login(client, "alice@example.com")


@pytest.fixture()
def other_headers(client):
    return register_and_login(client, "bob@example.com")

@pytest.fixture(autouse=True)
def fake_redis(monkeypatch):
    # A fresh, private fake server per test, so limits never leak between tests.
    server = fakeredis.FakeServer()
    monkeypatch.setattr(
        rate_limit, "redis_client", fakeredis.FakeRedis(server=server, decode_responses=True)
    )