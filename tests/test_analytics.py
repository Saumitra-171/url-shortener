import json
from datetime import datetime, timedelta, timezone

import pytest

from app.core.useragent import classify_browser
from app.models.url import URL
from app.services.click_worker import QUEUE_KEY

CHROME = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/118.0.0.0 Safari/537.36"
EDGE = CHROME + " Edg/118.0.2088.46"
OPERA = CHROME + " OPR/104.0.0.0"
FIREFOX = "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:109.0) Gecko/20100101 Firefox/118.0"
SAFARI = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Safari/605.1.15"
CHROME_IOS = "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) CriOS/118.0.5993.69 Mobile/15E148 Safari/604.1"
GOOGLEBOT = "Mozilla/5.0 (compatible; Googlebot/2.1; +http://www.google.com/bot.html)"
CURL = "curl/8.21.0"


def make_link(client, headers):
    response = client.post("/shorten", json={"url": "https://example.com"}, headers=headers)
    return response.json()["short_code"]


def url_id(session_factory, code):
    with session_factory() as db:
        return db.query(URL).filter_by(short_code=code).one().id


def queue_click(fake_redis, uid, when, referrer=None, user_agent=None):
    fake_redis.lpush(QUEUE_KEY, json.dumps({
        "url_id": uid, "ts": when.isoformat(),
        "referrer": referrer, "user_agent": user_agent, "ip": "1.2.3.4",
    }))


def summary(client, headers, code, days=30):
    return client.get(f"/{code}/analytics/summary", params={"days": days}, headers=headers)


def test_empty_link_has_a_full_zeroed_series(client, auth_headers):
    code = make_link(client, auth_headers)
    body = summary(client, auth_headers, code).json()

    assert body["days"] == 30
    assert len(body["clicks_per_day"]) == 30
    assert all(d["clicks"] == 0 for d in body["clicks_per_day"])
    assert body["clicks_per_day"][-1]["date"] == datetime.now(timezone.utc).date().isoformat()
    assert body["total_clicks"] == 0
    assert body["top_referrers"] == [] and body["browsers"] == []


def test_clicks_are_grouped_per_day_with_gaps_filled(
    client, auth_headers, session_factory, fake_redis, flush_clicks
):
    code = make_link(client, auth_headers)
    uid = url_id(session_factory, code)
    now = datetime.now(timezone.utc)
    queue_click(fake_redis, uid, now)
    queue_click(fake_redis, uid, now)
    queue_click(fake_redis, uid, now - timedelta(days=2))
    flush_clicks()

    body = summary(client, auth_headers, code).json()

    assert [d["clicks"] for d in body["clicks_per_day"][-3:]] == [1, 0, 2]  # two days ago, yesterday, today
    assert body["total_clicks"] == 3


def test_clicks_outside_the_window_are_excluded(client, auth_headers, session_factory, fake_redis, flush_clicks):
    code = make_link(client, auth_headers)
    uid = url_id(session_factory, code)
    now = datetime.now(timezone.utc)
    queue_click(fake_redis, uid, now - timedelta(days=40))
    queue_click(fake_redis, uid, now)
    flush_clicks()

    assert summary(client, auth_headers, code, days=30).json()["total_clicks"] == 1
    assert summary(client, auth_headers, code, days=60).json()["total_clicks"] == 2


def test_top_referrers_are_ranked_and_direct_is_labelled(
    client, auth_headers, session_factory, fake_redis, flush_clicks
):
    code = make_link(client, auth_headers)
    uid = url_id(session_factory, code)
    now = datetime.now(timezone.utc)
    for _ in range(3):
        queue_click(fake_redis, uid, now, referrer="https://a.example/")
    queue_click(fake_redis, uid, now, referrer="https://b.example/")
    for _ in range(2):
        queue_click(fake_redis, uid, now, referrer=None)
    flush_clicks()

    assert summary(client, auth_headers, code).json()["top_referrers"] == [
        {"referrer": "https://a.example/", "clicks": 3},
        {"referrer": "(direct)", "clicks": 2},
        {"referrer": "https://b.example/", "clicks": 1},
    ]


def test_only_the_top_five_referrers_are_returned(client, auth_headers, session_factory, fake_redis, flush_clicks):
    code = make_link(client, auth_headers)
    uid = url_id(session_factory, code)
    for i in range(6):
        queue_click(fake_redis, uid, datetime.now(timezone.utc), referrer=f"https://site{i}.example/")
    flush_clicks()

    assert len(summary(client, auth_headers, code).json()["top_referrers"]) == 5


def test_browsers_are_counted_from_real_redirects(client, auth_headers, flush_clicks):
    code = make_link(client, auth_headers)
    for user_agent, times in ((CHROME, 3), (FIREFOX, 2), (CURL, 1)):
        for _ in range(times):
            client.get(f"/{code}", headers={"user-agent": user_agent}, follow_redirects=False)
    flush_clicks()

    assert summary(client, auth_headers, code).json()["browsers"] == [
        {"browser": "Chrome", "clicks": 3},
        {"browser": "Firefox", "clicks": 2},
        {"browser": "Bot/Tool", "clicks": 1},
    ]


@pytest.mark.parametrize(
    "user_agent, expected",
    [
        (CHROME, "Chrome"),
        (EDGE, "Edge"),          # contains "Chrome" and "Safari" too
        (OPERA, "Opera"),        # contains "Chrome" and "Safari" too
        (FIREFOX, "Firefox"),
        (SAFARI, "Safari"),
        (CHROME_IOS, "Chrome"),  # says "CriOS", not "Chrome"
        (GOOGLEBOT, "Bot/Tool"),
        (CURL, "Bot/Tool"),
        (None, "Unknown"),
    ],
)
def test_classify_browser(user_agent, expected):
    assert classify_browser(user_agent) == expected


def test_other_user_cannot_see_the_summary(client, auth_headers, other_headers):
    code = make_link(client, auth_headers)
    assert summary(client, other_headers, code).status_code == 404
    assert summary(client, auth_headers, code).status_code == 200


@pytest.mark.parametrize("days", [0, 91])
def test_days_must_be_between_1_and_90(client, auth_headers, days):
    code = make_link(client, auth_headers)
    assert summary(client, auth_headers, code, days=days).status_code == 422


def test_summary_requires_login(client, auth_headers):
    code = make_link(client, auth_headers)
    assert client.get(f"/{code}/analytics/summary").status_code == 401