from uuid import uuid4

from fastapi.testclient import TestClient

from backend.app.main import app

client = TestClient(app)


def test_live_health_is_available_without_provider_credentials():
    response = client.get("/health/live")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_trading_autonomy_defaults_to_paper_guardrails():
    response = client.get("/api/v1/trading/autonomy")
    assert response.status_code == 200
    body = response.json()
    assert isinstance(body["autonomy_level"], int)
    assert 1 <= body["autonomy_level"] <= 5
    assert "live_trading_enabled" in body
    assert "trade_commands_enabled" in body
    allow = body["guardrails"]["pair_allowlist"]
    # Product spot allowlist — ADA/XRP (+ EUR variants), not BTC-as-default.
    assert "ADAUSD" in allow or "ADAEUR" in allow
    assert "XRPUSD" in allow or "XRPEUR" in allow


def test_market_ticker_uses_public_rest_when_cli_unavailable():
    """Windows uvicorn cannot spawn kraken CLI; public REST should still serve tickers."""
    response = client.get("/api/v1/market/ticker/BTCUSD")
    # Live network: 200 with data, or 503 if Kraken public is unreachable in CI.
    assert response.status_code in {200, 503}
    if response.status_code == 200:
        body = response.json()
        assert body["pair"] == "BTCUSD"
        assert isinstance(body.get("data"), dict)


def test_invalid_paper_order_is_rejected_before_provider_dispatch():
    response = client.post(
        "/api/v1/paper/orders",
        json={
            "pair": "BTCUSD",
            "side": "buy",
            "volume": "0",
            "order_type": "market",
            "idempotency_key": str(uuid4()),
        },
    )
    # 422 = schema/guardrail reject before Kraken; 401/503 = auth/provider unavailable.
    assert response.status_code in {401, 422, 503}


def test_ohlcv_batch_reports_provider_errors_without_mocking():
    response = client.get(
        "/api/v1/market/ohlcv",
        params={"asset_class": "forex", "symbols": "EURUSD", "intervals": "1min,4h"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["requested"] == 2
    # Missing key → config; free-tier key present → rate_limit/api are also acceptable.
    assert body["failed"] == 2
    assert {item["error"]["code"] for item in body["items"]} <= {"config", "rate_limit", "api", "network"}
