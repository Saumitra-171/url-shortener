import json
import time

import pytest
import redis

from app.models.click import Click
from app.models.url import URL
from app.services import click_worker
from app.services.click_worker import DEAD_KEY, QUEUE_KEY, ClickWorker


def shorten(client, headers, alias=None):
    body = {"url": "https://example.com"}
    if alias:
        body["alias"] = alias
    return client.post("/shorten", json=body, headers=headers).json()["short_code"]


def click_count(client, headers, code):
    return client.get(f"/{code}/analytics", headers=headers).json()["stats"]["click_count"]


def test_redirect_queues_the_click_instead_of_writing_it(client, auth_headers, fake_redis, flush_clicks):
    code = shorten(client, auth_headers)
    assert client.get(f"/{code}", follow_redirects=False).status_code == 302

    assert fake_redis.llen(QUEUE_KEY) == 1
    assert click_count(client, auth_headers, code) == 0  # not in the database yet

    flush_clicks()
    assert fake_redis.llen(QUEUE_KEY) == 0
    assert click_count(client, auth_headers, code) == 1


def test_clicks_are_processed_in_batches(client, auth_headers, session_factory):
    code = shorten(client, auth_headers)
    for _ in range(25):
        client.get(f"/{code}", follow_redirects=False)

    ClickWorker(session_factory, batch_size=10, backoff_base=0).drain()  # 10 + 10 + 5

    assert click_count(client, auth_headers, code) == 25
    with session_factory() as db:
        assert db.query(Click).count() == 25


def test_click_keeps_the_time_it_happened(client, auth_headers, session_factory, fake_redis, flush_clicks):
    shorten(client, auth_headers)
    with session_factory() as db:
        url_id = db.query(URL).one().id
    fake_redis.lpush(QUEUE_KEY, json.dumps({
        "url_id": url_id, "ts": "2020-01-01T00:00:00+00:00",
        "referrer": None, "user_agent": "test", "ip": "1.2.3.4",
    }))

    flush_clicks()

    with session_factory() as db:
        assert db.query(Click).one().clicked_at.year == 2020  # not the processing time


def test_redis_outage_falls_back_to_a_direct_write(client, auth_headers, monkeypatch):
    code = shorten(client, auth_headers)

    class BrokenRedis:
        def pipeline(self, *args, **kwargs):
            raise redis.ConnectionError("down")

    monkeypatch.setattr(click_worker, "redis_client", BrokenRedis())

    assert client.get(f"/{code}", follow_redirects=False).status_code == 302
    assert click_count(client, auth_headers, code) == 1  # written immediately, no worker involved


def test_clicks_for_deleted_links_do_not_poison_the_batch(client, auth_headers, fake_redis, flush_clicks):
    shorten(client, auth_headers, alias="keep-me")
    shorten(client, auth_headers, alias="gone-soon")
    client.get("/keep-me", follow_redirects=False)
    client.get("/gone-soon", follow_redirects=False)
    assert client.delete("/gone-soon", headers=auth_headers).status_code == 204

    flush_clicks()

    assert click_count(client, auth_headers, "keep-me") == 1
    assert fake_redis.llen(DEAD_KEY) == 0


def test_transient_database_failure_is_retried(client, auth_headers, session_factory, monkeypatch):
    code = shorten(client, auth_headers)
    client.get(f"/{code}", follow_redirects=False)

    real = click_worker._write_batch
    calls = {"n": 0}

    def flaky(db, events):
        calls["n"] += 1
        if calls["n"] < 3:
            raise RuntimeError("db hiccup")
        return real(db, events)

    monkeypatch.setattr(click_worker, "_write_batch", flaky)
    ClickWorker(session_factory, backoff_base=0).drain()

    assert calls["n"] == 3
    assert click_count(client, auth_headers, code) == 1


def test_batch_that_keeps_failing_goes_to_the_dead_letter_queue(
    client, auth_headers, session_factory, fake_redis, monkeypatch
):
    code = shorten(client, auth_headers)
    for _ in range(3):
        client.get(f"/{code}", follow_redirects=False)

    def always_fail(db, events):
        raise RuntimeError("db down")

    monkeypatch.setattr(click_worker, "_write_batch", always_fail)
    ClickWorker(session_factory, max_retries=3, backoff_base=0).drain()

    assert fake_redis.llen(QUEUE_KEY) == 0
    assert fake_redis.llen(DEAD_KEY) == 3


def test_malformed_event_is_dead_lettered_and_good_ones_still_land(
    client, auth_headers, fake_redis, flush_clicks
):
    code = shorten(client, auth_headers)
    client.get(f"/{code}", follow_redirects=False)
    fake_redis.lpush(QUEUE_KEY, "this is not json")

    flush_clicks()

    assert fake_redis.llen(DEAD_KEY) == 1
    assert click_count(client, auth_headers, code) == 1


def test_queue_is_capped(fake_redis, monkeypatch):
    monkeypatch.setattr(click_worker, "MAX_QUEUE", 3)
    for i in range(5):
        assert click_worker.enqueue_click(i, None, None, None) is True
    assert fake_redis.llen(QUEUE_KEY) == 3


def test_background_thread_drains_the_queue(client, auth_headers, session_factory, fake_redis):
    code = shorten(client, auth_headers)
    worker = ClickWorker(session_factory, min_poll=0.01, max_poll=0.05, backoff_base=0)
    worker.start()
    try:
        for _ in range(5):
            client.get(f"/{code}", follow_redirects=False)
        deadline = time.time() + 5
        while fake_redis.llen(QUEUE_KEY) and time.time() < deadline:
            time.sleep(0.02)
    finally:
        worker.stop()  # joins the thread, so the last write has finished

    assert click_count(client, auth_headers, code) == 5