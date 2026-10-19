import pytest
import redis

from app.core import rate_limit


@pytest.fixture()
def clock(monkeypatch):
    state = {"now": 1_000_000.0}
    monkeypatch.setattr(rate_limit, "_now", lambda: state["now"])
    return state


def test_allows_up_to_limit_then_blocks(clock):
    results = [rate_limit.hit("k", 3, 60)[0] for _ in range(5)]
    assert results == [True, True, True, False, False]


def test_window_slides(clock):
    for _ in range(3):
        rate_limit.hit("k", 3, 60)
    assert rate_limit.hit("k", 3, 60)[0] is False
    clock["now"] += 61
    assert rate_limit.hit("k", 3, 60)[0] is True


def test_retry_after_counts_down_from_the_oldest_request(clock):
    for _ in range(3):
        rate_limit.hit("k", 3, 60)
    clock["now"] += 10
    allowed, retry_after = rate_limit.hit("k", 3, 60)
    assert allowed is False
    assert retry_after == 50


def test_shorten_is_limited_per_user(client, auth_headers, other_headers):
    body = {"url": "https://example.com"}
    for _ in range(10):
        assert client.post("/shorten", json=body, headers=auth_headers).status_code == 201

    blocked = client.post("/shorten", json=body, headers=auth_headers)
    assert blocked.status_code == 429
    assert int(blocked.headers["Retry-After"]) >= 1

    # a different user has their own budget
    assert client.post("/shorten", json=body, headers=other_headers).status_code == 201


def test_login_attempts_are_throttled(client):
    client.post("/auth/register", json={"email": "a@example.com", "password": "password123"})
    codes = [
        client.post("/auth/login", data={"username": "a@example.com", "password": "wrong"}).status_code
        for _ in range(6)
    ]
    assert codes == [401, 401, 401, 401, 401, 429]


def test_redis_outage_does_not_block_requests(client, auth_headers, monkeypatch):
    class BrokenRedis:
        def pipeline(self, *args, **kwargs):
            raise redis.ConnectionError("down")

    monkeypatch.setattr(rate_limit, "redis_client", BrokenRedis())
    response = client.post("/shorten", json={"url": "https://example.com"}, headers=auth_headers)
    assert response.status_code == 201