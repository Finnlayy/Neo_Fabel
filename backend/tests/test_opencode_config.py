"""OpenCode config builder."""

from __future__ import annotations

from backend.app.integrations.opencode_config import build_opencode_config
from backend.app.settings import Settings


def test_opencode_config_shape() -> None:
    settings = Settings(
        aiprimetech_api_key="sk-test",
        aiprimetech_base_url="https://aiprimetech.io/v1",
    )
    payload = build_opencode_config(settings, include_api_key=True)
    assert payload["$schema"] == "https://opencode.ai/config.json"
    openai = payload["provider"]["openai"]
    assert openai["options"]["baseURL"] == "https://aiprimetech.io/v1"
    assert openai["options"]["apiKey"] == "sk-test"
    assert "gpt-5.4-mini" in openai["models"]
    mini = openai["models"]["gpt-5.4-mini"]
    assert mini["limit"]["context"] == 400_000
    assert mini["options"]["store"] is False
    assert set(mini["variants"]) == {"low", "medium", "high", "xhigh"}
    assert payload["agent"]["build"]["options"]["store"] is False


def test_opencode_config_redacts_key() -> None:
    settings = Settings(aiprimetech_api_key="sk-secret")
    payload = build_opencode_config(settings, include_api_key=False)
    assert "apiKey" not in payload["provider"]["openai"]["options"]
