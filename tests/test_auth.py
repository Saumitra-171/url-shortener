import pytest

from app.core.config import settings
from app.core.security import decode_access_token
from app.models.url import URL
from app.models.user import User

CREDS = {"email": "alice@example.com", "password": "password123"}


def login(client, email=CREDS["email"], password=CREDS["password"]):
    return client.post("/auth/login", data={"username": email, "password": password})


def shorten(client, headers):
    response = client.post("/shorten", json={"url": "https://example.com"}, headers=headers)
    return response.json()["short_code"]


# ---------- registration ----------

def test_register_normalizes_email_and_hides_password(client):
    response = client.post("/auth/register", json={"email": "Alice@Example.com", "password": "password123"})
    assert response.status_code == 201
    body = response.json()
    assert body["email"] == "alice@example.com"
    assert "password" not in body and "hashed_password" not in body


def test_password_is_stored_hashed(client, session_factory):
    client.post("/auth/register", json=CREDS)
    with session_factory() as db:
        stored = db.query(User).one().hashed_password
    assert stored != CREDS["password"]
    assert stored.startswith("$2b$")


def test_duplicate_email_is_rejected_case_insensitively(client):
    assert client.post("/auth/register", json=CREDS).status_code == 201
    again = client.post("/auth/register", json={**CREDS, "email": "ALICE@example.com"})
    assert again.status_code == 409


@pytest.mark.parametrize(
    "payload",
    [
        {"email": "not-an-email", "password": "password123"},
        {"email": "a@example.com", "password": "short"},
        {"email": "a@example.com", "password": "x" * 73},
    ],
)
def test_register_validation(client, payload):
    assert client.post("/auth/register", json=payload).status_code == 422


# ---------- login and tokens ----------

def test_login_returns_a_valid_token(client):
    client.post("/auth/register", json=CREDS)
    response = login(client)
    assert response.status_code == 200
    body = response.json()
    assert body["token_type"] == "bearer"
    assert isinstance(decode_access_token(body["access_token"]), int)


def test_wrong_password_and_unknown_email_look_identical(client):
    client.post("/auth/register", json=CREDS)
    wrong = login(client, password="not-the-password")
    unknown = login(client, email="ghost@example.com")
    assert wrong.status_code == unknown.status_code == 401
    assert wrong.json() == unknown.json()


def test_me_requires_a_valid_token(client, auth_headers):
    assert client.get("/auth/me").status_code == 401
    assert client.get("/auth/me", headers={"Authorization": "Bearer garbage"}).status_code == 401
    response = client.get("/auth/me", headers=auth_headers)
    assert response.status_code == 200
    assert response.json()["email"] == "alice@example.com"


def test_tampered_token_is_rejected(client, auth_headers):
    tampered = {"Authorization": auth_headers["Authorization"] + "x"}
    assert client.get("/auth/me", headers=tampered).status_code == 401


def test_expired_token_is_rejected(client, monkeypatch):
    client.post("/auth/register", json=CREDS)
    monkeypatch.setattr(settings, "access_token_expire_minutes", -1)  # tokens born already expired
    token = login(client).json()["access_token"]
    response = client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 401


# ---------- ownership ----------

def test_shorten_requires_login(client):
    assert client.post("/shorten", json={"url": "https://example.com"}).status_code == 401


def test_redirect_stays_public(client, auth_headers):
    code = shorten(client, auth_headers)
    assert client.get(f"/{code}", follow_redirects=False).status_code == 302


def test_url_is_owned_by_its_creator(client, auth_headers, session_factory):
    shorten(client, auth_headers)
    with session_factory() as db:
        owner = db.query(User).filter_by(email="alice@example.com").one()
        assert db.query(URL).one().owner_id == owner.id


def test_other_user_cannot_see_analytics(client, auth_headers, other_headers):
    code = shorten(client, auth_headers)
    assert client.get(f"/{code}/analytics", headers=other_headers).status_code == 404
    assert client.get(f"/{code}/analytics", headers=auth_headers).status_code == 200


def test_other_user_cannot_delete(client, auth_headers, other_headers):
    code = shorten(client, auth_headers)
    assert client.delete(f"/{code}", headers=other_headers).status_code == 404
    assert client.get(f"/{code}", follow_redirects=False).status_code == 302  # still alive
    assert client.delete(f"/{code}", headers=auth_headers).status_code == 204