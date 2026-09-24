"""The production server: API under /api, the React app everywhere else."""

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def web_client(tmp_path, monkeypatch):
    # A fake "built frontend" so the test doesn't depend on running npm.
    (tmp_path / "index.html").write_text("<html>FitFlow app</html>", encoding="utf-8")
    (tmp_path / "assets").mkdir()
    (tmp_path / "assets" / "app.js").write_text("console.log('hi')", encoding="utf-8")
    monkeypatch.setenv("FRONTEND_DIST", str(tmp_path))

    import importlib

    import fitflow.web
    importlib.reload(fitflow.web)  # re-read FRONTEND_DIST
    with TestClient(fitflow.web.web) as client:
        yield client


def test_api_is_served_under_api(web_client):
    assert web_client.get("/api/health").json() == {"status": "ok"}


def test_static_files_are_served(web_client):
    assert web_client.get("/assets/app.js").text == "console.log('hi')"


def test_app_routes_fall_back_to_index_html(web_client):
    # Refreshing the browser on /chat must load the React app, not a 404.
    for path in ("/", "/chat", "/progress"):
        assert "FitFlow app" in web_client.get(path).text
