"""Multi-provider LLM router: ordered failover across Gemini + OpenAI-compatible APIs."""

from __future__ import annotations

import itertools
import logging
from typing import Any

import httpx

from ..settings import Settings
from .aiprimetech_catalog import AIPRIMETECH_BASE_URL, list_models_public
from .gemini_client import (
    AiNotConfigured,
    GeminiClient,
    _parse_json_object,
    _route_label,
)
from .llm_spend import (
    DailyBudgetExceeded,
    assert_budget_available,
    estimate_cost_eur,
    provider_spend_payload,
    record_spend,
    tokens_from_messages,
)

logger = logging.getLogger(__name__)

# Never log secrets — only provider names / status codes.


class ProviderTransientError(Exception):
    """Rate-limit, server error, or timeout — safe to fail over to the next provider."""

    def __init__(self, provider: str, message: str, *, status: int | None = None):
        self.provider = provider
        self.status = status
        super().__init__(f"{provider}: {message}")


# OpenAI-compatible free/gateway providers (same /v1/chat/completions shape).
_OPENAI_COMPAT: dict[str, dict[str, str]] = {
    "openrouter": {
        "base_url": "https://openrouter.ai/api/v1",
        "label": "OpenRouter",
    },
    "groq": {
        "base_url": "https://api.groq.com/openai/v1",
        "label": "Groq",
    },
    "cerebras": {
        "base_url": "https://api.cerebras.ai/v1",
        "label": "Cerebras",
    },
    "aiprimetech": {
        "base_url": AIPRIMETECH_BASE_URL,
        "label": "AIPrimeTech",
    },
}

_KNOWN_PROVIDERS = frozenset({"gemini", *_OPENAI_COMPAT.keys()})

# Module-level counter for optional round-robin among configured providers.
_rotate_counter = itertools.count(0)


def reset_llm_router_rotate_for_tests() -> None:
    global _rotate_counter
    _rotate_counter = itertools.count(0)


class LlmRouter:
    """Facade matching GeminiClient chat/JSON surface with provider failover."""

    def __init__(self, settings: Settings):
        self.settings = settings
        self._gemini = GeminiClient(settings)

    @property
    def configured(self) -> bool:
        return bool(self.configured_providers())

    def configured_providers(self) -> list[str]:
        """Providers that have credentials (order follows AI_PROVIDER_ORDER)."""
        return [name for name in self.provider_order() if self._is_configured(name)]

    def provider_order(self) -> list[str]:
        raw = (self.settings.ai_provider_order or "").strip()
        if not raw:
            return ["gemini", "openrouter", "groq", "cerebras", "aiprimetech"]
        names: list[str] = []
        for part in raw.split(","):
            name = part.strip().lower()
            if name and name in _KNOWN_PROVIDERS and name not in names:
                names.append(name)
        return names or ["gemini", "openrouter", "groq", "cerebras", "aiprimetech"]

    def status_payload(self) -> dict[str, Any]:
        chain = self.configured_providers()
        primary = chain[0] if chain and self.settings.ai_chat_enabled else None
        payload: dict[str, Any] = {
            "configured": bool(primary),
            "provider": primary or "none",
            "providers": chain,
            "provider_order": self.provider_order(),
            "active_chain": chain,
            "deterministic_fallback": self.settings.ai_allow_deterministic_fallback,
            "chat_enabled": self.settings.ai_chat_enabled,
            "rotate": self.settings.ai_provider_rotate,
        }
        if self._is_configured("aiprimetech"):
            budget = float(self.settings.aiprimetech_daily_budget_eur)
            spend = {**provider_spend_payload("aiprimetech", budget), "tracked": True}
            payload["aiprimetech"] = {
                "base_url": (self.settings.aiprimetech_base_url or AIPRIMETECH_BASE_URL).rstrip("/"),
                "default_model": self.settings.aiprimetech_default_model,
                "daily_budget_eur": budget,
                "models": list_models_public(),
                **spend,
            }
            payload["spend"] = spend
        else:
            payload["spend"] = {
                "day": None,
                "provider": primary or "none",
                "spent_eur": 0.0,
                "limit_eur": 0.0,
                "remaining_eur": 0.0,
                "calls_today": 0,
                "budget_exhausted": False,
                "budget_used_pct": 0.0,
                "prompt_tokens": 0,
                "completion_tokens": 0,
                "total_tokens": 0,
                "event_count": 0,
                "tracked": False,
            }
        return payload

    def _is_configured(self, name: str) -> bool:
        if name == "gemini":
            return bool(self.settings.gemini_api_key)
        if name == "openrouter":
            return bool(self.settings.openrouter_api_key)
        if name == "groq":
            return bool(self.settings.groq_api_key)
        if name == "cerebras":
            return bool(self.settings.cerebras_api_key)
        if name == "aiprimetech":
            return bool(self.settings.aiprimetech_api_key)
        return False

    def _api_key(self, name: str) -> str | None:
        if name == "openrouter":
            return self.settings.openrouter_api_key
        if name == "groq":
            return self.settings.groq_api_key
        if name == "cerebras":
            return self.settings.cerebras_api_key
        if name == "aiprimetech":
            return self.settings.aiprimetech_api_key
        return None

    def _default_model(self, name: str) -> str:
        if name == "openrouter":
            return self.settings.openrouter_default_model
        if name == "groq":
            return self.settings.groq_default_model
        if name == "cerebras":
            return self.settings.cerebras_default_model
        if name == "aiprimetech":
            return self.settings.aiprimetech_default_model
        return self.settings.gemini_default_model

    def _compat_base_url(self, provider: str) -> str:
        if provider == "aiprimetech":
            return (self.settings.aiprimetech_base_url or AIPRIMETECH_BASE_URL).rstrip("/")
        return _OPENAI_COMPAT[provider]["base_url"].rstrip("/")

    def _chain_for_attempt(self) -> list[str]:
        chain = self.configured_providers()
        if not chain:
            return []
        if not self.settings.ai_provider_rotate or len(chain) < 2:
            return chain
        start = next(_rotate_counter) % len(chain)
        return chain[start:] + chain[:start]

    async def generate_text(
        self,
        *,
        messages: list[dict[str, str]],
        model_selection: str = "auto",
        system: str | None = None,
    ) -> dict[str, Any]:
        errors: list[str] = []
        chain = self._chain_for_attempt()
        for name in chain:
            try:
                if name == "gemini":
                    result = await self._gemini_generate_text(
                        messages=messages,
                        model_selection=model_selection,
                        system=system,
                    )
                else:
                    result = await self._openai_compatible_chat(
                        provider=name,
                        messages=messages,
                        system=system,
                        model_selection=model_selection,
                    )
                return result
            except DailyBudgetExceeded as exc:
                logger.info("LLM skip %s (budget): %s", name, exc)
                errors.append(str(exc))
                continue
            except ProviderTransientError as exc:
                logger.info("LLM failover after %s", exc)
                errors.append(str(exc))
                continue

        if self.settings.ai_allow_deterministic_fallback:
            last = next((m["content"] for m in reversed(messages) if m.get("role") == "user"), "")
            return {
                "reply": (
                    "[deterministic-fallback] No live LLM provider answered. "
                    f"Echoing last user prompt ({len(last)} chars). "
                    "Set GEMINI_API_KEY / OPENROUTER_API_KEY / GROQ_API_KEY / AIPRIMETECH_API_KEY for live replies."
                ),
                "modelUsed": "deterministic-fallback",
                "routeLabel": "Deterministic Fallback",
                "provider": "deterministic",
                "citations": [],
            }

        detail = "; ".join(errors[:3]) if errors else "no providers configured"
        raise AiNotConfigured(
            f"No LLM provider available ({detail}). "
            "Configure GEMINI_API_KEY, OPENROUTER_API_KEY, GROQ_API_KEY, or AIPRIMETECH_API_KEY."
        )

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
        """Vision stays Gemini-only (other free tiers lack a common vision path)."""
        return await self._gemini.analyze_image(image=image, mime_type=mime_type, prompt=prompt)

    async def _gemini_generate_text(
        self,
        *,
        messages: list[dict[str, str]],
        model_selection: str,
        system: str | None,
    ) -> dict[str, Any]:
        # Bypass GeminiClient's own deterministic path — router owns failover/fallback.
        if not self._gemini.configured:
            raise ProviderTransientError("gemini", "not configured")

        model = self._gemini.resolve_model(model_selection)
        contents: list[dict[str, Any]] = []
        for message in messages:
            role = "user" if message.get("role") != "assistant" else "model"
            contents.append({"role": role, "parts": [{"text": message.get("content", "")}]})

        payload: dict[str, Any] = {"contents": contents}
        if system:
            payload["systemInstruction"] = {"parts": [{"text": system}]}

        data = await self._gemini_post(f"/models/{model}:generateContent", payload)
        from .gemini_client import _extract_text

        text = _extract_text(data)
        return {
            "reply": text,
            "modelUsed": model,
            "routeLabel": _route_label(model_selection),
            "provider": "gemini",
            "citations": [],
        }

    async def _gemini_post(self, path: str, payload: dict[str, Any]) -> dict[str, Any]:
        key = self.settings.gemini_api_key
        assert key
        url = f"{self._gemini.base}{path}"
        timeout = self.settings.gemini_timeout_seconds
        try:
            async with httpx.AsyncClient(timeout=timeout) as client:
                response = await client.post(url, params={"key": key}, json=payload)
        except httpx.TimeoutException as exc:
            raise ProviderTransientError("gemini", "timeout", status=None) from exc
        except httpx.TransportError as exc:
            raise ProviderTransientError("gemini", f"transport error: {exc}", status=None) from exc

        if response.status_code in {429} or response.status_code >= 500:
            raise ProviderTransientError(
                "gemini",
                f"HTTP {response.status_code}",
                status=response.status_code,
            )
        if response.status_code >= 400:
            if response.status_code in {401, 403}:
                raise ProviderTransientError(
                    "gemini",
                    f"HTTP {response.status_code}",
                    status=response.status_code,
                )
            raise RuntimeError(f"Gemini HTTP {response.status_code}: {response.text[:400]}")
        return response.json()

    async def _openai_compatible_chat(
        self,
        *,
        provider: str,
        messages: list[dict[str, str]],
        system: str | None,
        model_selection: str,
    ) -> dict[str, Any]:
        meta = _OPENAI_COMPAT[provider]
        key = self._api_key(provider)
        if not key:
            raise ProviderTransientError(provider, "not configured")

        budget_limit = 0.0
        if provider == "aiprimetech":
            budget_limit = float(self.settings.aiprimetech_daily_budget_eur)
            assert_budget_available(provider, budget_limit)

        model = self._default_model(provider)
        oai_messages: list[dict[str, str]] = []
        if system:
            oai_messages.append({"role": "system", "content": system})
        for message in messages:
            role = message.get("role") or "user"
            if role == "system":
                oai_messages.append({"role": "system", "content": message.get("content", "")})
            elif role == "assistant":
                oai_messages.append({"role": "assistant", "content": message.get("content", "")})
            else:
                oai_messages.append({"role": "user", "content": message.get("content", "")})

        url = f"{self._compat_base_url(provider)}/chat/completions"
        headers = {
            "Authorization": f"Bearer {key}",
            "Content-Type": "application/json",
        }
        if provider == "openrouter":
            headers["HTTP-Referer"] = "https://github.com/neo-fabel/neo-fabel"
            headers["X-Title"] = "Neo Fabel"

        body: dict[str, Any] = {"model": model, "messages": oai_messages}
        if provider == "aiprimetech":
            # opencode store:false — avoid remote retention when the gateway supports it.
            body["store"] = False

        timeout = self.settings.ai_llm_timeout_seconds
        try:
            async with httpx.AsyncClient(timeout=timeout) as client:
                response = await client.post(url, headers=headers, json=body)
        except httpx.TimeoutException as exc:
            raise ProviderTransientError(provider, "timeout", status=None) from exc
        except httpx.TransportError as exc:
            raise ProviderTransientError(provider, f"transport error: {exc}", status=None) from exc

        if response.status_code == 429 or response.status_code >= 500:
            raise ProviderTransientError(
                provider,
                f"HTTP {response.status_code}",
                status=response.status_code,
            )
        if response.status_code >= 400:
            if response.status_code in {401, 403}:
                raise ProviderTransientError(
                    provider,
                    f"HTTP {response.status_code}",
                    status=response.status_code,
                )
            raise RuntimeError(
                f"{meta['label']} HTTP {response.status_code}: {response.text[:400]}"
            )

        data = response.json()
        choices = data.get("choices") or []
        text = ""
        if choices:
            msg = (choices[0] or {}).get("message") or {}
            text = str(msg.get("content") or "").strip()
        used = str(data.get("model") or model)
        label = meta["label"]
        if model_selection and model_selection != "auto":
            route = f"{label} ({model_selection})"
        else:
            route = label

        result: dict[str, Any] = {
            "reply": text,
            "modelUsed": used,
            "routeLabel": route,
            "provider": provider,
            "citations": [],
        }

        if provider == "aiprimetech":
            usage = data.get("usage") or {}
            prompt_tokens = int(usage.get("prompt_tokens") or 0)
            completion_tokens = int(usage.get("completion_tokens") or 0)
            if prompt_tokens <= 0 and completion_tokens <= 0:
                prompt_tokens, completion_tokens = tokens_from_messages(oai_messages, text)
            cost = estimate_cost_eur(
                model=model,
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                input_eur_per_1m=self.settings.aiprimetech_eur_per_1m_input,
                output_eur_per_1m=self.settings.aiprimetech_eur_per_1m_output,
            )
            snap = record_spend(
                provider,
                cost_eur=cost,
                model=used,
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                limit_eur=budget_limit,
            )
            result["costEur"] = cost
            result["budget"] = {
                "spent_eur": snap.spent_eur,
                "remaining_eur": snap.remaining_eur,
                "limit_eur": snap.limit_eur,
                "calls_today": snap.calls,
            }

        return result
