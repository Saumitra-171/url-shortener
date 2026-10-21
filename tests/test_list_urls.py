from datetime import datetime, timedelta, timezone

import pytest


def make(client, headers, alias=None, **extra):
    body = {"url": "https://example.com", **extra}
    if alias:
        body["alias"] = alias
    response = client.post("/shorten", json=body, headers=headers)
    assert response.status_code == 201
    return response.json()["short_code"]


def codes(client, headers, **params):
    response = client.get("/urls", params=params, headers=headers)
    assert response.status_code == 200
    return [item["short_code"] for item in response.json()]


def test_requires_login(client):
    assert client.get("/urls").status_code == 401  # not 404 from the redirect route


def test_empty_list_for_a_new_user(client, auth_headers):
    assert codes(client, auth_headers) == []


def test_only_my_links_are_listed(client, auth_headers, other_headers):
    make(client, auth_headers, alias="alice-link")
    make(client, other_headers, alias="bob-link")
    assert codes(client, auth_headers) == ["alice-link"]
    assert codes(client, other_headers) == ["bob-link"]


def test_newest_first(client, auth_headers):
    for i in (1, 2, 3):
        make(client, auth_headers, alias=f"link-{i}")
    assert codes(client, auth_headers) == ["link-3", "link-2", "link-1"]


def test_pagination(client, auth_headers):
    for i in range(1, 6):
        make(client, auth_headers, alias=f"link-{i}")
    assert codes(client, auth_headers, limit=2) == ["link-5", "link-4"]
    assert codes(client, auth_headers, limit=2, offset=2) == ["link-3", "link-2"]
    assert codes(client, auth_headers, limit=2, offset=4) == ["link-1"]
    assert codes(client, auth_headers, limit=2, offset=10) == []


@pytest.mark.parametrize("params", [{"limit": 0}, {"limit": 101}, {"offset": -1}])
def test_pagination_parameters_are_validated(client, auth_headers, params):
    assert client.get("/urls", params=params, headers=auth_headers).status_code == 422


def test_urls_is_a_reserved_alias(client, auth_headers):
    for alias in ("urls", "URLS"):
        response = client.post("/shorten", json={"url": "https://example.com", "alias": alias}, headers=auth_headers)
        assert response.status_code == 422


def test_list_reflects_clicks_after_the_worker_runs(client, auth_headers, flush_clicks):
    code = make(client, auth_headers)
    client.get(f"/{code}", follow_redirects=False)
    flush_clicks()
    item = client.get("/urls", headers=auth_headers).json()[0]
    assert item["click_count"] == 1
    assert item["short_url"].endswith("/" + code)


def test_expiry_is_included(client, auth_headers):
    soon = (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat()
    make(client, auth_headers, alias="expiring", expires_at=soon)
    make(client, auth_headers, alias="forever")
    items = {i["short_code"]: i for i in client.get("/urls", headers=auth_headers).json()}
    assert items["expiring"]["expires_at"] is not None
    assert items["forever"]["expires_at"] is None