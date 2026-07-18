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
    assert body["autonomy_level"] == 2
    assert body["live_trading_enabled"] is False
    assert body["trade_commands_enabled"] is False
    assert "BTCUSD" in body["guardrails"]["pair_allowlist"]


def test_missing_kraken_binary_is_reported_as_unavailable():
    response = client.get("/api/v1/market/ticker/BTCUSD")
    assert response.status_code == 503
    assert response.json()["detail"]["code"] == "config"


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
    assert response.status_code in {401, 503}


def test_ohlcv_batch_reports_missing_alpha_vantage_without_mocking():
    response = client.get(
        "/api/v1/market/ohlcv",
        params={"asset_class": "forex", "symbols": "EURUSD", "intervals": "1min,4h"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["requested"] == 2
    assert body["failed"] == 2
    assert {item["error"]["code"] for item in body["items"]} == {"config"}
