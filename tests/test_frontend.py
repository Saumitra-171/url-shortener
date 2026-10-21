import pytest

import app.main as main_module


@pytest.fixture()
def built(tmp_path, monkeypatch):
    """A tiny fake build, so the tests never depend on the real frontend being built."""
    dist = tmp_path / "dist"
    (dist / "assets").mkdir(parents=True)
    (dist / "index.html").write_text("<html><div id='root'>SPA-INDEX</div></html>")
    (dist / "assets" / "index-abc123.js").write_text("console.log('bundle')")
    (dist / "favicon.svg").write_text("<svg>ICON</svg>")
    (tmp_path / "secret.txt").write_text("TOP-SECRET")  # sits OUTSIDE the build folder
    monkeypatch.setattr(main_module, "FRONTEND_DIR", dist)
    return dist


def test_root_redirects_to_the_app(client, built):
    response = client.get("/", follow_redirects=False)
    assert response.status_code == 302
    assert response.headers["location"] == "/app/"


def test_app_without_trailing_slash_redirects(client, built):
    response = client.get("/app", follow_redirects=False)
    assert response.status_code == 302
    assert response.headers["location"] == "/app/"


def test_app_serves_the_index(client, built):
    response = client.get("/app/")
    assert response.status_code == 200
    assert "SPA-INDEX" in response.text


def test_client_side_routes_fall_back_to_the_index(client, built):
    for path in ("/app/login", "/app/links/Alias-key"):
        response = client.get(path)
        assert response.status_code == 200
        assert "SPA-INDEX" in response.text


def test_assets_are_served_and_cached_forever(client, built):
    response = client.get("/app/assets/index-abc123.js")
    assert response.status_code == 200
    assert response.text == "console.log('bundle')"
    assert "immutable" in response.headers["cache-control"]


def test_index_is_never_cached(client, built):
    assert client.get("/app/").headers["cache-control"] == "no-cache"


def test_top_level_static_files_are_served(client, built):
    response = client.get("/app/favicon.svg")
    assert response.status_code == 200
    assert "ICON" in response.text


@pytest.mark.parametrize("path", ["/app/..%2Fsecret.txt", "/app/%2e%2e/secret.txt"])
def test_path_traversal_is_blocked(client, built, path):
    response = client.get(path)
    assert "TOP-SECRET" not in response.text


def test_missing_build_gives_404(client, tmp_path, monkeypatch):
    monkeypatch.setattr(main_module, "FRONTEND_DIR", tmp_path / "missing")
    assert client.get("/app/").status_code == 404
    assert client.get("/app/login").status_code == 404


def test_api_routes_are_unaffected(client, built):
    assert client.get("/health").json()["status"] == "ok"
    assert client.get("/urls").status_code == 401  # still the API, not the index page