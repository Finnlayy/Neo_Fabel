"""Gemini Generative Language API client (httpx) with optional deterministic fallback."""

from __future__ import annotations

import base64
import json
import re
from typing import Any

import httpx

from ..settings import Settings


class AiNotConfigured(Exception):
    """Raised when Gemini is required but GEMINI_API_KEY is missing."""


MODEL_MAP = {
    "auto": "gemini-2.0-flash",
    "flash": "gemini-2.0-flash",
    "flash-lite": "gemini-2.0-flash-lite",
    "pro-preview": "gemini-2.0-flash",
}


def _strip_data_url(image: str) -> tuple[str, str | None]:
    match = re.match(r"^data:([^;]+);base64,(.+)$", image, flags=re.DOTALL)
    if match:
        return match.group(2), match.group(1)
    return image, None


class GeminiClient:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.base = "https://generativelanguage.googleapis.com/v1beta"

    @property
    def configured(self) -> bool:
        return bool(self.settings.gemini_api_key)

    def resolve_model(self, selection: str) -> str:
        return MODEL_MAP.get(selection, self.settings.gemini_default_model)

    async def generate_text(
        self,
        *,
        messages: list[dict[str, str]],
        model_selection: str = "auto",
        system: str | None = None,
    ) -> dict[str, Any]:
        if not self.configured:
            if self.settings.ai_allow_deterministic_fallback:
                last = next((m["content"] for m in reversed(messages) if m.get("role") == "user"), "")
                return {
                    "reply": (
                        "[deterministic-fallback] Gemini is not configured. "
                        f"Echoing last user prompt ({len(last)} chars). Set GEMINI_API_KEY for live replies."
                    ),
                    "modelUsed": "deterministic-fallback",
                    "routeLabel": "Deterministic Fallback",
                    "citations": [],
                }
            raise AiNotConfigured("GEMINI_API_KEY is not configured")

        model = self.resolve_model(model_selection)
        contents: list[dict[str, Any]] = []
        for message in messages:
            role = "user" if message.get("role") != "assistant" else "model"
            contents.append({"role": role, "parts": [{"text": message.get("content", "")}]})

        payload: dict[str, Any] = {"contents": contents}
        if system:
            payload["systemInstruction"] = {"parts": [{"text": system}]}

        data = await self._post(f"/models/{model}:generateContent", payload)
        text = _extract_text(data)
        return {
            "reply": text,
            "modelUsed": model,
            "routeLabel": _route_label(model_selection),
            "citations": [],
        }

    async def generate_json(
        self,
        *,
        prompt: str,
        system: str,
        model_selection: str = "flash",
    ) -> dict[str, Any]:
        result = await self.generate_text(
            messages=[{"role": "user", "content": prompt}],
            model_selection=model_selection,
            system=system + "\nRespond with JSON only.",
        )
        return _parse_json_object(result["reply"])

    async def analyze_image(
        self,
        *,
        image: str,
        mime_type: str,
        prompt: str,
    ) -> str:
        if not self.configured:
            if self.settings.ai_allow_deterministic_fallback:
                return (
                    "[deterministic-fallback] Chart vision unavailable without GEMINI_API_KEY. "
                    f"Received {mime_type} image ({len(image)} chars). Prompt mode noted."
                )
            raise AiNotConfigured("GEMINI_API_KEY is not configured")

        raw_b64, detected = _strip_data_url(image)
        mime = detected or mime_type or "image/png"
        model = self.settings.gemini_default_model
        payload = {
            "contents": [
                {
                    "role": "user",
                    "parts": [
                        {"text": prompt},
                        {"inline_data": {"mime_type": mime, "data": raw_b64}},
                    ],
                }
            ]
        }
        data = await self._post(f"/models/{model}:generateContent", payload)
        return _extract_text(data)

    async def _post(self, path: str, payload: dict[str, Any]) -> dict[str, Any]:
        key = self.settings.gemini_api_key
        assert key
        url = f"{self.base}{path}"
        async with httpx.AsyncClient(timeout=self.settings.gemini_timeout_seconds) as client:
            response = await client.post(url, params={"key": key}, json=payload)
            if response.status_code >= 400:
                raise RuntimeError(f"Gemini HTTP {response.status_code}: {response.text[:400]}")
            return response.json()


def _route_label(selection: str) -> str:
    return {
        "auto": "Auto Router",
        "flash": "Flash Core",
        "flash-lite": "Low-Latency Core",
        "pro-preview": "Pro Preview",
    }.get(selection, "Gemini")


def _extract_text(data: dict[str, Any]) -> str:
    candidates = data.get("candidates") or []
    if not candidates:
        return ""
    parts = ((candidates[0] or {}).get("content") or {}).get("parts") or []
    chunks = [str(part.get("text", "")) for part in parts if isinstance(part, dict)]
    return "\n".join(chunk for chunk in chunks if chunk).strip()


def _parse_json_object(text: str) -> dict[str, Any]:
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned)
        cleaned = re.sub(r"\s*```$", "", cleaned)
    try:
        parsed = json.loads(cleaned)
        if isinstance(parsed, dict):
            return parsed
    except json.JSONDecodeError:
        pass
    match = re.search(r"\{[\s\S]*\}", cleaned)
    if match:
        parsed = json.loads(match.group(0))
        if isinstance(parsed, dict):
            return parsed
    raise ValueError("model did not return a JSON object")


def deterministic_plan(prompt: str) -> dict[str, Any]:
    """Bare GenerativePlan when Gemini is unavailable and fallback is allowed."""
    snippet = (prompt or "balanced crypto rotation").strip()[:120]
    return {
        "planTitle": f"Paper plan: {snippet}",
        "summary": (
            "Deterministic orchestration fallback (GEMINI_API_KEY unset). "
            "Allocates a conservative paper basket; replace with live Gemini for real directives."
        ),
        "subAgentDirectives": {
            "marketData": "Poll Kraken paper tickers for BTC/ETH/SOL; ignore equities until AV configured.",
            "adaptiveAgent": "Stay flat unless 15m change exceeds 2% absolute on allowlisted pairs.",
            "rnaSmartelligent": "Prefer mean-reversion on SOL; avoid leverage >1x in paper mode.",
            "riskGovernor": "Hard stop at 2% session drawdown; max 3 open paper positions.",
        },
        "resourceAllocation": [
            {"name": "BTC", "value": 40},
            {"name": "ETH", "value": 30},
            {"name": "SOL", "value": 20},
            {"name": "USD", "value": 10},
        ],
        "suggestedRules": [
            "Paper orders only via /api/v1/paper/orders",
            "No live Kraken execution from this plan",
            f"User intent retained: {snippet}",
        ],
    }


def deterministic_trade_analysis(trades: list[dict[str, Any]]) -> str:
    count = len(trades)
    completed = [t for t in trades if str(t.get("status", "")).upper() == "COMPLETED"]
    pnl = sum(float(t.get("pnl") or 0) for t in completed)
    wins = sum(1 for t in completed if float(t.get("pnl") or 0) > 0)
    return (
        f"[deterministic-fallback] Reviewed {count} trade row(s), {len(completed)} completed. "
        f"Realized PnL sum={pnl:.2f}, wins={wins}. "
        "Set GEMINI_API_KEY for model-authored diagnostics."
    )


def decode_image_size_hint(image: str) -> int:
    raw, _ = _strip_data_url(image)
    try:
        return len(base64.b64decode(raw, validate=False))
    except Exception:
        return len(image)
