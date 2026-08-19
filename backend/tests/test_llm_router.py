"""Unit tests for multi-provider LLM failover (mocked httpx — no real API calls)."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from backend.app.integrations.gemini_client import AiNotConfigured
from backend.app.integrations.llm_router import (
    LlmRouter,
    ProviderTransientError,
    reset_llm_router_rotate_for_tests,
)
from backend.app.settings import Settings, get_settings


def _settings(**overrides) -> Settings:
    get_settings.cache_clear()
    base = {
        "gemini_api_key": None,
        "openrouter_api_key": None,
        "groq_api_key": None,
        "cerebras_api_key": None,
        "ai_allow_deterministic_fallback": False,
        "ai_provider_order": "gemini,openrouter,groq,cerebras",
        "ai_provider_rotate": False,
        "ai_chat_enabled": True,
        "openrouter_default_model": "qwen/qwen3-coder:free",
        "groq_default_model": "llama-3.1-8b-instant",
        "cerebras_default_model": "llama3.1-8b",
        "ai_llm_timeout_seconds": 5.0,
        "gemini_timeout_seconds": 5.0,
    }
    base.update(overrides)
    return Settings(**base)


def _mock_response(status: int, json_body: dict | None = None, text: str = "") -> MagicMock:
    resp = MagicMock(spec=httpx.Response)
    resp.status_code = status
    resp.text = text or ("" if json_body is None else str(json_body))
    resp.json.return_value = json_body or {}
    return resp


@pytest.fixture(autouse=True)
def _clear_settings_cache():
    get_settings.cache_clear()
    reset_llm_router_rotate_for_tests()
    yield
    get_settings.cache_clear()
    reset_llm_router_rotate_for_tests()


@pytest.mark.asyncio
async def test_failover_on_429_uses_second_provider():
    settings = _settings(gemini_api_key="g-key", openrouter_api_key="or-key")
    router = LlmRouter(settings)

    gemini_resp = _mock_response(429, text="rate limited")
    or_resp = _mock_response(
        200,
        {
            "model": "qwen/qwen3-coder:free",
            "choices": [{"message": {"content": "hello from openrouter"}}],
        },
    )

    mock_client = AsyncMock()
    mock_client.post = AsyncMock(side_effect=[gemini_resp, or_resp])
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)

    with patch("backend.app.integrations.llm_router.httpx.AsyncClient", return_value=mock_client):
        result = await router.generate_text(
            messages=[{"role": "user", "content": "hi"}],
            model_selection="flash",
            system="test",
        )

    assert result["provider"] == "openrouter"
    assert result["reply"] == "hello from openrouter"
    assert result["modelUsed"] == "qwen/qwen3-coder:free"
    assert "OpenRouter" in result["routeLabel"]
    assert mock_client.post.await_count == 2


@pytest.mark.asyncio
async def test_success_on_first_provider_skips_rest():
    settings = _settings(gemini_api_key="g-key", openrouter_api_key="or-key")
    router = LlmRouter(settings)

    gemini_resp = _mock_response(
        200,
        {
            "candidates": [
                {"content": {"parts": [{"text": "gemini reply"}]}}
            ]
        },
    )
    mock_client = AsyncMock()
    mock_client.post = AsyncMock(return_value=gemini_resp)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)

    with patch("backend.app.integrations.llm_router.httpx.AsyncClient", return_value=mock_client):
        result = await router.generate_text(
            messages=[{"role": "user", "content": "hi"}],
            model_selection="auto",
        )

    assert result["provider"] == "gemini"
    assert result["reply"] == "gemini reply"
    assert mock_client.post.await_count == 1


@pytest.mark.asyncio
async def test_unconfigured_raises_without_deterministic():
    router = LlmRouter(_settings())
    with pytest.raises(AiNotConfigured):
        await router.generate_text(messages=[{"role": "user", "content": "hi"}])


@pytest.mark.asyncio
async def test_deterministic_fallback_when_enabled():
    router = LlmRouter(_settings(ai_allow_deterministic_fallback=True))
    result = await router.generate_text(messages=[{"role": "user", "content": "paper plan"}])
    assert result["provider"] == "deterministic"
    assert "deterministic-fallback" in result["reply"]


def test_status_lists_configured_providers():
    router = LlmRouter(
        _settings(
            gemini_api_key="",
            openrouter_api_key="or-key",
            groq_api_key="g-key",
            ai_provider_order="gemini,openrouter,groq,cerebras",
        )
    )
    status = router.status_payload()
    assert status["configured"] is True
    assert status["provider"] == "openrouter"
    assert status["active_chain"] == ["openrouter", "groq"]
    assert status["provider_order"][0] == "gemini"
    assert "cerebras" in status["provider_order"]


def test_status_none_when_no_keys():
    status = LlmRouter(_settings()).status_payload()
    assert status["configured"] is False
    assert status["provider"] == "none"
    assert status["active_chain"] == []


@pytest.mark.asyncio
async def test_timeout_fails_over_to_groq():
    settings = _settings(openrouter_api_key="or-key", groq_api_key="gq-key")
    router = LlmRouter(settings)

    groq_resp = _mock_response(
        200,
        {
            "model": "llama-3.1-8b-instant",
            "choices": [{"message": {"content": "from groq"}}],
        },
    )

    call_count = {"n": 0}

    async def _post(*_args, **_kwargs):
        call_count["n"] += 1
        if call_count["n"] == 1:
            raise httpx.TimeoutException("slow")
        return groq_resp

    mock_client = AsyncMock()
    mock_client.post = AsyncMock(side_effect=_post)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)

    with patch("backend.app.integrations.llm_router.httpx.AsyncClient", return_value=mock_client):
        result = await router.generate_text(messages=[{"role": "user", "content": "hi"}])

    assert result["provider"] == "groq"
    assert result["reply"] == "from groq"


@pytest.mark.asyncio
async def test_provider_transient_error_message():
    err = ProviderTransientError("openrouter", "HTTP 429", status=429)
    assert err.provider == "openrouter"
    assert err.status == 429
    assert "openrouter" in str(err)
