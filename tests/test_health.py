import pytest
import redis

import app.main as main_module
from app.core.database import get_db
from app.main import app


def test_liveness(client):
    assert client.get("/health").json()["status"] == "ok"


def test_ready_when_everything_is_up(client, fake_redis, monkeypatch):
    monkeypatch.setattr(main_module, "redis_client", fake_redis)
    response = client.get("/health/ready")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "database": "up", "redis": "up"}


def test_ready_is_degraded_but_available_when_redis_is_down(client, monkeypatch):
    class BrokenRedis:
        def ping(self):
            raise redis.ConnectionError("down")

    monkeypatch.setattr(main_module, "redis_client", BrokenRedis())
    response = client.get("/health/ready")
    assert response.status_code == 200
    assert response.json()["status"] == "degraded"
    assert response.json()["redis"] == "down"


def test_ready_fails_when_the_database_is_down(client):
    class BrokenSession:
        def execute(self, *args, **kwargs):
            raise RuntimeError("db down")

    app.dependency_overrides[get_db] = lambda: BrokenSession()  # the client fixture clears this
    assert client.get("/health/ready").status_code == 503

def test_root_redirects_to_the_docs_when_the_app_is_not_built(client, monkeypatch, tmp_path):
    monkeypatch.setattr(main_module, "FRONTEND_DIR", tmp_path / "missing")
    response = client.get("/", follow_redirects=False)
    assert response.status_code == 302
    assert response.headers["location"] == "/docs"