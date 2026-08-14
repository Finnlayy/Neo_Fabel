"""AIPrimeTech (OpenAI-compatible) model catalog — no secrets."""

from __future__ import annotations

from typing import Any

# Mirrors opencode provider.openai.models (aiprimetech.io gateway).
# Costs are conservative EUR estimates per 1M tokens for local budget metering
# (provider invoices may differ — tune via AIPRIMETECH_*_EUR_PER_1M_* env).
AIPRIMETECH_MODELS: dict[str, dict[str, Any]] = {
    "gpt-5.2": {
        "name": "GPT-5.2",
        "context": 400_000,
        "output": 128_000,
        "eur_per_1m_input": 2.0,
        "eur_per_1m_output": 8.0,
        "variants": ("low", "medium", "high", "xhigh"),
    },
    "gpt-5.6": {
        "name": "GPT-5.6 (Sol)",
        "context": 1_050_000,
        "output": 128_000,
        "eur_per_1m_input": 2.5,
        "eur_per_1m_output": 10.0,
        "variants": ("low", "medium", "high", "xhigh", "max"),
    },
    "gpt-5.6-sol": {
        "name": "GPT-5.6 Sol",
        "context": 1_050_000,
        "output": 128_000,
        "eur_per_1m_input": 2.5,
        "eur_per_1m_output": 10.0,
        "variants": ("low", "medium", "high", "xhigh", "max"),
    },
    "gpt-5.6-terra": {
        "name": "GPT-5.6 Terra",
        "context": 1_050_000,
        "output": 128_000,
        "eur_per_1m_input": 2.5,
        "eur_per_1m_output": 10.0,
        "variants": ("low", "medium", "high", "xhigh", "max"),
    },
    "gpt-5.6-luna": {
        "name": "GPT-5.6 Luna",
        "context": 1_050_000,
        "output": 128_000,
        "eur_per_1m_input": 2.5,
        "eur_per_1m_output": 10.0,
        "variants": ("low", "medium", "high", "xhigh", "max"),
    },
    "gpt-5.5": {
        "name": "GPT-5.5",
        "context": 1_050_000,
        "output": 128_000,
        "eur_per_1m_input": 2.2,
        "eur_per_1m_output": 9.0,
        "variants": ("low", "medium", "high", "xhigh"),
    },
    "gpt-5.4": {
        "name": "GPT-5.4",
        "context": 1_050_000,
        "output": 128_000,
        "eur_per_1m_input": 2.0,
        "eur_per_1m_output": 8.0,
        "variants": ("low", "medium", "high", "xhigh"),
    },
    "gpt-5.4-mini": {
        "name": "GPT-5.4 Mini",
        "context": 400_000,
        "output": 128_000,
        "eur_per_1m_input": 0.4,
        "eur_per_1m_output": 1.6,
        "variants": ("low", "medium", "high", "xhigh"),
    },
    "gpt-5.3-codex-spark": {
        "name": "GPT-5.3 Codex Spark",
        "context": 128_000,
        "output": 32_000,
        "eur_per_1m_input": 0.5,
        "eur_per_1m_output": 2.0,
        "variants": ("low", "medium", "high", "xhigh"),
    },
    "codex-mini-latest": {
        "name": "Codex Mini",
        "context": 200_000,
        "output": 100_000,
        "eur_per_1m_input": 0.3,
        "eur_per_1m_output": 1.2,
        "variants": ("low", "medium", "high"),
    },
}

DEFAULT_AIPRIMETECH_MODEL = "gpt-5.4-mini"
AIPRIMETECH_BASE_URL = "https://aiprimetech.io/v1"


def model_meta(model_id: str) -> dict[str, Any]:
    return AIPRIMETECH_MODELS.get(model_id) or AIPRIMETECH_MODELS[DEFAULT_AIPRIMETECH_MODEL]


def list_models_public() -> list[dict[str, Any]]:
    return [
        {
            "id": mid,
            "name": meta["name"],
            "context": meta["context"],
            "output": meta["output"],
            "variants": list(meta.get("variants") or ()),
        }
        for mid, meta in AIPRIMETECH_MODELS.items()
    ]
