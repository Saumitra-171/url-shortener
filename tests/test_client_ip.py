from starlette.requests import Request

from app.core.client import client_ip
from app.core.config import settings


def make_request(forwarded=None, peer=("10.0.0.1", 5000)):
    headers = [(b"x-forwarded-for", forwarded.encode())] if forwarded is not None else []
    scope = {"type": "http", "headers": headers}
    if peer:
        scope["client"] = peer
    return Request(scope)


def test_default_ignores_the_forwarded_header(monkeypatch):
    monkeypatch.setattr(settings, "trusted_proxy_hops", 0)
    assert client_ip(make_request("1.2.3.4")) == "10.0.0.1"


def test_one_trusted_hop_uses_the_last_entry_and_ignores_spoofing(monkeypatch):
    monkeypatch.setattr(settings, "trusted_proxy_hops", 1)
    # the client sent a fake 9.9.9.9, the trusted proxy appended the address it really saw
    assert client_ip(make_request("9.9.9.9, 203.0.113.7")) == "203.0.113.7"


def test_two_trusted_hops(monkeypatch):
    monkeypatch.setattr(settings, "trusted_proxy_hops", 2)
    assert client_ip(make_request("9.9.9.9, 203.0.113.7, 172.16.0.5")) == "203.0.113.7"


def test_falls_back_to_the_peer_when_the_header_is_too_short(monkeypatch):
    monkeypatch.setattr(settings, "trusted_proxy_hops", 2)
    assert client_ip(make_request("203.0.113.7")) == "10.0.0.1"


def test_no_client_at_all(monkeypatch):
    monkeypatch.setattr(settings, "trusted_proxy_hops", 0)
    assert client_ip(make_request(peer=None)) is None


def test_rate_limit_cannot_be_dodged_with_a_spoofed_header(client):
    client.post("/auth/register", json={"email": "a@example.com", "password": "password123"})
    codes = [
        client.post(
            "/auth/login",
            data={"username": "a@example.com", "password": "wrong"},
            headers={"X-Forwarded-For": f"8.8.8.{i}"},  # a different fake address each time
        ).status_code
        for i in range(6)
    ]
    assert codes == [401, 401, 401, 401, 401, 429]