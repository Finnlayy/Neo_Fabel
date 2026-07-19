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
    assert body["provider"] in {"none", "gemini"}


def test_tvapi_optimize_deterministic_with_auth(monkeypatch):
    app.dependency_overrides[require_user] = _fake_user
    try:
        monkeypatch.setenv("TVAPI_ENABLED", "true")
        get_settings.cache_clear()
        response = client.post(
            "/api/tvapi/optimize",
            headers={"Authorization": "Bearer test"},
            json={
                "strategy": "smc",
                "symbol": "BTCUSD",
                "timeframe": "5m",
                "minTrades": 30,
                "primaryObjective": "profit_factor",
                "secondaryObjective": "percent_profitable",
                "parameters": {"swingLength": 5},
            },
        )
        assert response.status_code == 200
        body = response.json()
        assert body["success"] is True
        assert body["winner"] is not None
        assert "deterministic" in body["bericht"].lower()
        assert isinstance(body["results"], list) and body["results"]
    finally:
        app.dependency_overrides.clear()
        get_settings.cache_clear()


def test_orchestrate_deterministic_fallback(monkeypatch):
    app.dependency_overrides[require_user] = _fake_user
    try:
        monkeypatch.setenv("GEMINI_API_KEY", "")
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


def test_chat_requires_auth():
    response = client.post("/api/chat", json={"messages": [{"role": "user", "content": "hi"}]})
    assert response.status_code in {401, 503}


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
