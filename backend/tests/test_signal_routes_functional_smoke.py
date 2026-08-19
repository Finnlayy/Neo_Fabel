"""Functional smoke — TestClient auth failures for status/routes/webhook (flags default off)."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from starlette.requests import Request

from backend.app.main import app
from backend.app.settings import Settings, get_settings

client = TestClient(app)


@pytest.fixture
def no_dev_bypass(monkeypatch):
    """Force real auth for smoke even when operator .env enables AUTH_DEV_BYPASS."""
    settings = get_settings()
    monkeypatch.setattr(settings, "auth_dev_bypass", False)
    return settings


def test_signal_automation_status_requires_auth(no_dev_bypass):
    response = client.get("/api/v1/signal-automation/status")
    assert response.status_code in {401, 403}
    body = response.json()
    blob = str(body).lower()
    assert "tvsec_" not in blob
    assert "pepper" not in blob


def test_signal_routes_list_requires_auth(no_dev_bypass):
    response = client.get("/api/v1/signal-routes")
    assert response.status_code in {401, 403}
    blob = str(response.json()).lower()
    assert "tvsec_" not in blob
    assert "mcptok_" not in blob


def test_webhook_unknown_route_fails_closed_when_flags_off(no_dev_bypass, monkeypatch):
    """Default-off product: ingress returns disabled, never executes."""
    monkeypatch.setattr(no_dev_bypass, "signal_routes_enabled", False)
    monkeypatch.setattr(no_dev_bypass, "tradingview_ingress_enabled", False)
    response = client.post(
        "/api/v1/webhooks/tradingview/missing-public-key",
        json={
            "schema_version": 1,
            "credential": "tvsec_abcdefghijklmnopqrstuvwxyz012345",
            "signal_id": "smoke-1",
            "occurred_at": "2026-07-18T12:00:00Z",
            "strategy_id": "S",
            "pair": "ADAUSD",
            "side": "buy",
            "volume": "1",
            "order_type": "market",
        },
    )
    # Flags off → 503 ingress_disabled; malformed natural parse may 422 first.
    assert response.status_code in {401, 422, 503}
    blob = str(response.json()).lower()
    assert "tvsec_abcdefghijklmnopqrstuvwxyz012345" not in blob


@pytest.mark.asyncio
async def test_webhook_unknown_route_auth_failed_when_ingress_enabled():
    """With ingress temporarily enabled, unknown route is generic auth_failed."""
    from backend.app.signals.router import tradingview_webhook

    settings = Settings(
        _env_file=None,
        signal_routes_enabled=True,
        tradingview_ingress_enabled=True,
        signal_credential_pepper="test-pepper",
        kraken_live_trading_enabled=False,
        kraken_autonomy_level=2,
    )
    body = (
        b'{"schema_version":1,"credential":"tvsec_abcdefghijklmnopqrstuvwxyz012345",'
        b'"signal_id":"smoke-unknown","occurred_at":"2026-07-18T12:00:00Z",'
        b'"strategy_id":"S","pair":"ADAUSD","side":"buy","volume":"1","order_type":"market"}'
    )
    scope = {
        "type": "http",
        "asgi": {"version": "3.0"},
        "http_version": "1.1",
        "method": "POST",
        "scheme": "http",
        "path": "/api/v1/webhooks/tradingview/no-such-route",
        "raw_path": b"/api/v1/webhooks/tradingview/no-such-route",
        "query_string": b"",
        "headers": [(b"content-type", b"application/json")],
        "client": ("127.0.0.1", 123),
        "server": ("test", 80),
    }

    async def receive():
        return {"type": "http.request", "body": body, "more_body": False}

    request = Request(scope, receive)
    response = MagicMock()
    session = AsyncMock()

    repo = MagicMock()
    repo.get_route_by_public_key = AsyncMock(return_value=None)

    with (
        patch("backend.app.signals.router.get_settings", return_value=settings),
        patch("backend.app.signals.service.SignalRepository", lambda _s: repo),
        pytest.raises(Exception) as exc,
    ):
        await tradingview_webhook("no-such-route", request, response, session=session)

    err = exc.value
    assert getattr(err, "status_code", None) == 401
    detail = getattr(err, "detail", {})
    assert detail.get("code") == "auth_failed"


def test_mcp_submit_disabled_by_default():
    response = client.post(
        "/api/v1/mcp/signals/submit",
        headers={"Authorization": "Bearer mcptok_should_not_leak"},
        json={
            "idempotency_key": str(uuid4()),
            "occurred_at": "2026-07-18T12:00:00Z",
            "strategy_id": "S",
            "pair": "ADAUSD",
            "side": "buy",
            "volume": "1",
            "order_type": "market",
        },
    )
    assert response.status_code == 503
    body = response.json()
    blob = str(body).lower()
    assert "mcptok_should_not_leak" not in blob
    detail = body.get("detail", body)
    code = detail.get("code") if isinstance(detail, dict) else None
    assert code in {"mcp_disabled", "ingress_disabled"} or "disabled" in blob


def test_nginx_webhook_has_body_cap_and_rate_limit():
    from pathlib import Path

    text = Path(__file__).resolve().parents[2].joinpath("nginx.conf").read_text(encoding="utf-8")
    assert "client_max_body_size 16k" in text
    assert "limit_req zone=tv_webhook" in text
    assert "limit_req_zone" in text
    assert "access_log off" in text


def test_live_api_health_and_webhook_curl_smoke():
    """If local :8000 is up, curl-style checks; otherwise skip without failing the gate."""
    import urllib.error
    import urllib.request

    try:
        with urllib.request.urlopen("http://127.0.0.1:8000/health/live", timeout=2) as resp:
            assert resp.status == 200
    except (urllib.error.URLError, TimeoutError, OSError):
        pytest.skip("local API :8000 not reachable")

    req = urllib.request.Request(
        "http://127.0.0.1:8000/api/v1/signal-routes",
        method="GET",
        headers={"Accept": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=3) as resp:
            # Dev bypass may allow 200 on loopback; still must be secret-free.
            body = resp.read().decode("utf-8", errors="replace").lower()
            assert "tvsec_" not in body
            assert "mcptok_" not in body
            assert "pepper" not in body
    except urllib.error.HTTPError as exc:
        assert exc.code in {401, 403}
        err_body = exc.read().decode("utf-8", errors="replace").lower()
        assert "tvsec_" not in err_body
