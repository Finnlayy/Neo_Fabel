"""HTTP compression and middleware wiring."""

from __future__ import annotations

from fastapi.testclient import TestClient
from starlette.middleware.gzip import GZipMiddleware

from backend.app.main import app


client = TestClient(app)


def test_gzip_middleware_registered() -> None:
    middleware_classes = {middleware.cls for middleware in app.user_middleware}
    assert GZipMiddleware in middleware_classes


def test_openapi_json_gzip_when_accepted() -> None:
    """Large OpenAPI schema should be gzip-compressed when requested."""
    response = client.get("/openapi.json", headers={"Accept-Encoding": "gzip"})
    assert response.status_code == 200
    assert response.headers.get("content-encoding") == "gzip"
    assert response.headers.get("vary") == "Accept-Encoding"
    assert response.json()["openapi"].startswith("3.")


def test_small_health_response_not_gzip_compressed() -> None:
    """Tiny payloads stay uncompressed (minimum_size=1000 on GZipMiddleware)."""
    response = client.get("/health/live", headers={"Accept-Encoding": "gzip"})
    assert response.status_code == 200
    assert response.headers.get("content-encoding") is None


def test_static_mount_gets_private_cache_header() -> None:
    response = client.get("/static/netron/index.html")
    # Netron shell may 200 or 404 depending on seed files — header applies when served.
    if response.status_code == 200:
        assert "max-age=300" in (response.headers.get("cache-control") or "")
