from datetime import datetime, timedelta, timezone

import pytest

from app.services import url_service


def iso(**delta) -> str:
    return (datetime.now(timezone.utc) + timedelta(**delta)).isoformat()


def post(client, headers, **extra):
    return client.post("/shorten", json={"url": "https://example.com", **extra}, headers=headers)


def jump_forward(monkeypatch, **delta):
    monkeypatch.setattr(url_service, "_now", lambda: datetime.now(timezone.utc) + timedelta(**delta))


# ---------- aliases ----------

def test_custom_alias_is_used(client, auth_headers):
    response = post(client, auth_headers, alias="my-link")
    assert response.status_code == 201
    assert response.json()["short_code"] == "my-link"
    assert response.json()["short_url"].endswith("/my-link")
    assert client.get("/my-link", follow_redirects=False).status_code == 302


def test_duplicate_alias_conflicts(client, auth_headers, other_headers):
    assert post(client, auth_headers, alias="taken").status_code == 201
    assert post(client, other_headers, alias="taken").status_code == 409
    assert client.get("/taken", follow_redirects=False).status_code == 302  # original untouched


def test_aliases_are_case_sensitive(client, auth_headers):
    assert post(client, auth_headers, alias="Promo").status_code == 201
    assert post(client, auth_headers, alias="promo").status_code == 201


@pytest.mark.parametrize("alias", ["ab", "has space", "x" * 33, "bad/slash", "docs", "AUTH"])
def test_invalid_or_reserved_alias_rejected(client, auth_headers, alias):
    assert post(client, auth_headers, alias=alias).status_code == 422


# ---------- expiry ----------

def test_response_includes_expiry(client, auth_headers):
    assert post(client, auth_headers).json()["expires_at"] is None
    assert post(client, auth_headers, expires_at=iso(hours=1)).json()["expires_at"] is not None


def test_expiry_in_the_past_is_rejected(client, auth_headers):
    assert post(client, auth_headers, expires_at=iso(hours=-1)).status_code == 422


def test_expired_link_returns_410_from_cache(client, auth_headers, monkeypatch):
    post(client, auth_headers, alias="soon", expires_at=iso(hours=1))
    assert client.get("/soon", follow_redirects=False).status_code == 302

    jump_forward(monkeypatch, hours=2)
    assert client.get("/soon", follow_redirects=False).status_code == 410


def test_expired_link_returns_410_from_database(client, auth_headers, fake_cache, monkeypatch):
    post(client, auth_headers, alias="soon", expires_at=iso(hours=1))
    jump_forward(monkeypatch, hours=2)
    fake_cache.clear()  # force the database path

    assert client.get("/soon", follow_redirects=False).status_code == 410


def test_owner_can_still_see_analytics_after_expiry(client, auth_headers, monkeypatch):
    post(client, auth_headers, alias="soon", expires_at=iso(hours=1))
    client.get("/soon", follow_redirects=False)  # one real click

    jump_forward(monkeypatch, hours=2)
    assert client.get("/soon", follow_redirects=False).status_code == 410

    stats = client.get("/soon/analytics", headers=auth_headers)
    assert stats.status_code == 200
    assert stats.json()["stats"]["click_count"] == 1  # the 410 did not count as a click


def test_cache_ttl_is_capped_by_expiry(client, auth_headers, monkeypatch):
    seen = {}
    monkeypatch.setattr(url_service, "cache_set", lambda key, value, ttl=3600: seen.__setitem__(key, ttl))
    post(client, auth_headers, alias="brief", expires_at=iso(seconds=120))
    assert 0 < seen["url:brief"] <= 120