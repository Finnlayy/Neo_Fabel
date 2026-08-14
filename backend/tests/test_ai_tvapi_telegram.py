"""Tests for AI / TVAPI / Telegram legacy routes."""

from fastapi.testclient import TestClient

from backend.app.auth import require_user
from backend.app.integrations import telegram_bot as telegram_module
from backend.app.main import app
from backend.app.settings import get_settings

client = TestClient(app)


async def _fake_user():
    return {
        "uid": "test-user",
        "email": "user@example.com",
        "email_verified": True,
        "firebase": {"sign_in_provider": "google.com"},
    }


def test_ai_health_available():
    response = client.get("/api/ai/health")
    assert response.status_code == 200
    body = response.json()
    assert "configured" in body
    assert body["provider"] in {"none", "gemini", "openrouter", "groq", "cerebras", "aiprimetech"}
    assert "active_chain" in body
    assert "provider_order" in body
    assert isinstance(body["active_chain"], list)


def test_tvapi_optimize_candle_backtest_with_auth(monkeypatch):
    app.dependency_overrides[require_user] = _fake_user
    try:
        monkeypatch.setenv("TVAPI_ENABLED", "true")
        get_settings.cache_clear()

        from backend.app.integrations.backtest.ema_grid import synthetic_candles

        async def _synth(symbol: str, timeframe: str, *, limit: int = 300):
            return synthetic_candles(symbol, n=limit), "synthetic-ohlcv"

        monkeypatch.setattr(
            "backend.app.integrations.tvapi_optimizer.fetch_optimize_candles",
            _synth,
        )

        response = client.post(
            "/api/tvapi/optimize",
            headers={"Authorization": "Bearer test"},
            json={
                "strategy": "ema_cross",
                "symbol": "BTCUSD",
                "timeframe": "5m",
                "minTrades": 1,
                "primaryObjective": "profit_factor",
                "secondaryObjective": "percent_profitable",
                "parameters": {"emaFast": 8, "emaSlow": 21},
            },
        )
        assert response.status_code == 200
        body = response.json()
        assert body["success"] is True
        assert body["winner"] is not None
        assert "candle" in body["bericht"].lower() or "candle" in str(body.get("source", "")).lower()
        assert isinstance(body["results"], list) and body["results"]
    finally:
        app.dependency_overrides.clear()
        get_settings.cache_clear()


def test_tvapi_chart_strategies_with_auth(monkeypatch):
    app.dependency_overrides[require_user] = _fake_user
    try:
        monkeypatch.setenv("TVAPI_ENABLED", "true")
        get_settings.cache_clear()
        response = client.post(
            "/api/tvapi/chart-strategies",
            headers={"Authorization": "Bearer test"},
            json={"symbol": "BTCUSD"},
        )
        assert response.status_code == 200
        body = response.json()
        assert body["success"] is True
        assert body["symbol"] == "BTCUSD"
        assert isinstance(body["strategies"], list) and body["strategies"]
        assert all("id" in row and "name" in row and "kind" in row for row in body["strategies"])
    finally:
        app.dependency_overrides.clear()
        get_settings.cache_clear()


def test_orchestrate_deterministic_fallback(monkeypatch):
    app.dependency_overrides[require_user] = _fake_user
    try:
        monkeypatch.setenv("GEMINI_API_KEY", "")
        monkeypatch.setenv("OPENROUTER_API_KEY", "")
        monkeypatch.setenv("GROQ_API_KEY", "")
        monkeypatch.setenv("CEREBRAS_API_KEY", "")
        monkeypatch.setenv("AI_ALLOW_DETERMINISTIC_FALLBACK", "true")
        monkeypatch.setenv("AI_CHAT_ENABLED", "true")
        get_settings.cache_clear()
        response = client.post(
            "/api/gemini/orchestrate",
            headers={"Authorization": "Bearer test"},
            json={"prompt": "rotate into SOL paper"},
        )
        assert response.status_code == 200
        body = response.json()
        assert "planTitle" in body
        assert "resourceAllocation" in body
        assert "subAgentDirectives" in body
    finally:
        app.dependency_overrides.clear()
        get_settings.cache_clear()


def test_chat_requires_auth_when_dev_bypass_off(monkeypatch):
    monkeypatch.setenv("AUTH_DEV_BYPASS", "false")
    get_settings.cache_clear()
    try:
        response = client.post("/api/chat", json={"messages": [{"role": "user", "content": "hi"}]})
        assert response.status_code in {401, 503}
    finally:
        get_settings.cache_clear()


def test_chat_wire_returns_context_meta(monkeypatch):
    app.dependency_overrides[require_user] = _fake_user
    try:
        monkeypatch.setenv("GEMINI_API_KEY", "")
        monkeypatch.setenv("OPENROUTER_API_KEY", "")
        monkeypatch.setenv("GROQ_API_KEY", "")
        monkeypatch.setenv("CEREBRAS_API_KEY", "")
        monkeypatch.setenv("AI_ALLOW_DETERMINISTIC_FALLBACK", "true")
        monkeypatch.setenv("AI_CHAT_ENABLED", "true")
        get_settings.cache_clear()
        long_history = [{"role": "user", "content": f"turn-{i}"} for i in range(20)]
        long_history.append({"role": "user", "content": "latest question"})
        response = client.post(
            "/api/chat",
            headers={"Authorization": "Bearer test"},
            json={"messages": long_history, "modelSelection": "flash"},
        )
        assert response.status_code == 200
        body = response.json()
        assert body["success"] is True
        assert body.get("context") is not None
        assert body["context"]["input_messages"] == 21
        assert body["context"]["sent_messages"] <= 12
        assert body["context"]["trimmed"] is True
    finally:
        app.dependency_overrides.clear()
        get_settings.cache_clear()


def test_telegram_messages_empty_when_unconfigured(monkeypatch):
    app.dependency_overrides[require_user] = _fake_user
    try:
        telegram_module.reset_telegram_state_for_tests()
        monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "")
        monkeypatch.setenv("TELEGRAM_CHAT_ID", "")
        get_settings.cache_clear()
        response = client.get("/api/telegram/messages", headers={"Authorization": "Bearer test"})
        assert response.status_code == 200
        assert response.json() == []
    finally:
        app.dependency_overrides.clear()
        get_settings.cache_clear()
