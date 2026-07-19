"""AIPrimeTech daily EUR budget gate tests."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from backend.app.integrations.llm_router import LlmRouter, reset_llm_router_rotate_for_tests
from backend.app.integrations.llm_spend import (
    DailyBudgetExceeded,
    assert_budget_available,
    estimate_cost_eur,
    record_spend,
    reset_spend_for_tests,
)
from backend.app.settings import Settings, get_settings


def _settings(**overrides) -> Settings:
    get_settings.cache_clear()
    base = {
        "gemini_api_key": None,
        "openrouter_api_key": None,
        "groq_api_key": None,
        "cerebras_api_key": None,
        "aiprimetech_api_key": "test-key",
        "aiprimetech_daily_budget_eur": 1.0,
        "aiprimetech_default_model": "gpt-5.4-mini",
        "ai_allow_deterministic_fallback": False,
        "ai_provider_order": "aiprimetech",
        "ai_provider_rotate": False,
        "ai_chat_enabled": True,
        "ai_llm_timeout_seconds": 5.0,
    }
    base.update(overrides)
    return Settings(**base)


def _mock_response(status: int, json_body: dict | None = None) -> MagicMock:
    resp = MagicMock(spec=httpx.Response)
    resp.status_code = status
    resp.text = ""
    resp.json.return_value = json_body or {}
    return resp


@pytest.fixture(autouse=True)
def _clean():
    get_settings.cache_clear()
    reset_llm_router_rotate_for_tests()
    reset_spend_for_tests("aiprimetech")
    yield
    reset_spend_for_tests("aiprimetech")
    get_settings.cache_clear()
    reset_llm_router_rotate_for_tests()


def test_estimate_cost_mini_is_small() -> None:
    cost = estimate_cost_eur(model="gpt-5.4-mini", prompt_tokens=1000, completion_tokens=500)
    assert 0 < cost < 0.01


def test_budget_blocks_after_exhaustion() -> None:
    record_spend(
        "aiprimetech",
        cost_eur=1.0,
        model="gpt-5.4-mini",
        prompt_tokens=1,
        completion_tokens=1,
        limit_eur=1.0,
    )
    with pytest.raises(DailyBudgetExceeded):
        assert_budget_available("aiprimetech", 1.0)


@pytest.mark.asyncio
async def test_aiprimetech_records_budget_on_success() -> None:
    settings = _settings()
    router = LlmRouter(settings)
    resp = _mock_response(
        200,
        {
            "model": "gpt-5.4-mini",
            "choices": [{"message": {"content": "ok"}}],
            "usage": {"prompt_tokens": 100, "completion_tokens": 50},
        },
    )
    mock_client = AsyncMock()
    mock_client.post = AsyncMock(return_value=resp)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)

    with patch("backend.app.integrations.llm_router.httpx.AsyncClient", return_value=mock_client):
        result = await router.generate_text(messages=[{"role": "user", "content": "hi"}])

    assert result["provider"] == "aiprimetech"
    assert result["budget"]["limit_eur"] == 1.0
    assert result["budget"]["spent_eur"] > 0
    assert result["budget"]["remaining_eur"] < 1.0
    status = router.status_payload()
    assert status["aiprimetech"]["daily_budget_eur"] == 1.0
    assert status["aiprimetech"]["calls_today"] == 1


@pytest.mark.asyncio
async def test_aiprimetech_skipped_when_budget_gone() -> None:
    record_spend(
        "aiprimetech",
        cost_eur=1.0,
        model="gpt-5.4-mini",
        prompt_tokens=1,
        completion_tokens=1,
        limit_eur=1.0,
    )
    settings = _settings(
        openrouter_api_key="or-key",
        ai_provider_order="aiprimetech,openrouter",
    )
    router = LlmRouter(settings)
    or_resp = _mock_response(
        200,
        {"model": "free", "choices": [{"message": {"content": "from or"}}]},
    )
    mock_client = AsyncMock()
    mock_client.post = AsyncMock(return_value=or_resp)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)

    with patch("backend.app.integrations.llm_router.httpx.AsyncClient", return_value=mock_client):
        result = await router.generate_text(messages=[{"role": "user", "content": "hi"}])

    assert result["provider"] == "openrouter"
    assert result["reply"] == "from or"
