from app.models.click import Click
from app.models.url import URL


def make_url(client, headers, target="https://example.com"):
    response = client.post("/shorten", json={"url": target}, headers=headers)
    assert response.status_code == 201
    return response.json()


def test_shorten_returns_short_url(client, auth_headers):
    data = make_url(client, auth_headers)
    assert data["original_url"] == "https://example.com"
    assert data["short_url"].endswith("/" + data["short_code"])
    assert len(data["short_code"]) == 6


def test_shorten_warms_cache(client, auth_headers, fake_cache):
    code = make_url(client, auth_headers)["short_code"]
    assert f"url:{code}" in fake_cache


def test_invalid_url_rejected(client, auth_headers):
    response = client.post("/shorten", json={"url": "not a url"}, headers=auth_headers)
    assert response.status_code == 422


def test_redirect_is_302_and_counts_click(client, auth_headers):
    code = make_url(client, auth_headers)["short_code"]

    response = client.get(f"/{code}", follow_redirects=False)  # public, no headers

    assert response.status_code == 302
    assert response.headers["location"] == "https://example.com"
    stats = client.get(f"/{code}/analytics", headers=auth_headers).json()["stats"]
    assert stats["click_count"] == 1


def test_unknown_code_returns_404(client):
    assert client.get("/nope123", follow_redirects=False).status_code == 404


def test_delete_removes_url_and_its_clicks(client, auth_headers, session_factory):
    code = make_url(client, auth_headers)["short_code"]
    client.get(f"/{code}", follow_redirects=False)  # creates a click row

    assert client.delete(f"/{code}", headers=auth_headers).status_code == 204

    assert client.get(f"/{code}", follow_redirects=False).status_code == 404
    with session_factory() as db:
        assert db.query(URL).count() == 0
        assert db.query(Click).count() == 0