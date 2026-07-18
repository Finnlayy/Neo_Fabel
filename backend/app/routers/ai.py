"""AI chat, orchestrate, and trade-analysis routes (legacy /api paths)."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException

from ..auth import require_user
from ..integrations.gemini_client import (
    AiNotConfigured,
    GeminiClient,
    deterministic_plan,
    deterministic_trade_analysis,
)
from ..schemas_ai import (
    AnalyzeTradesRequest,
    AnalyzeTradesResponse,
    ChatRequest,
    ChatResponse,
    OrchestrateRequest,
)
from ..settings import Settings, get_settings

router = APIRouter(tags=["ai"])


def _client(settings: Settings | None = None) -> GeminiClient:
    return GeminiClient(settings or get_settings())


@router.get("/api/ai/health")
async def ai_health() -> dict[str, Any]:
    settings = get_settings()
    configured = bool(settings.gemini_api_key) and settings.ai_chat_enabled
    return {
        "configured": configured,
        "provider": "gemini" if configured else "none",
        "deterministic_fallback": settings.ai_allow_deterministic_fallback,
        "chat_enabled": settings.ai_chat_enabled,
    }


@router.post("/api/chat", response_model=ChatResponse)
async def chat(payload: ChatRequest, _user: dict = Depends(require_user)) -> ChatResponse:
    settings = get_settings()
    if not settings.ai_chat_enabled:
        return ChatResponse(success=False, error="AI chat is disabled (AI_CHAT_ENABLED=false)")
    client = _client(settings)
    try:
        result = await client.generate_text(
            messages=[m.model_dump() for m in payload.messages],
            model_selection=payload.modelSelection,
            system=(
                "You are Neo Fabel's paper-trading assistant. Prefer Pine Script v5, "
                "risk controls, and paper-only execution guidance. Never instruct live order placement."
            ),
        )
        return ChatResponse(
            success=True,
            reply=result["reply"],
            modelUsed=result["modelUsed"],
            routeLabel=result["routeLabel"],
            citations=result.get("citations") or [],
        )
    except AiNotConfigured as exc:
        return ChatResponse(success=False, error=str(exc))
    except Exception as exc:  # noqa: BLE001 — surface provider errors to UI
        return ChatResponse(success=False, error=str(exc))


@router.post("/api/gemini/orchestrate")
async def orchestrate(payload: OrchestrateRequest, _user: dict = Depends(require_user)) -> dict[str, Any]:
    settings = get_settings()
    if not settings.ai_chat_enabled:
        raise HTTPException(status_code=503, detail={"code": "ai_disabled", "message": "AI_CHAT_ENABLED=false"})

    client = _client(settings)
    system = (
        "Return a JSON object with keys: planTitle, summary, subAgentDirectives "
        "(marketData, adaptiveAgent, rnaSmartelligent, riskGovernor), "
        "resourceAllocation (array of {name, value} summing ~100), suggestedRules (string array). "
        "Paper trading only."
    )
    try:
        if not client.configured:
            if settings.ai_allow_deterministic_fallback:
                return deterministic_plan(payload.prompt)
            raise AiNotConfigured("GEMINI_API_KEY is not configured")
        plan = await client.generate_json(prompt=payload.prompt, system=system, model_selection="flash")
        return _normalize_plan(plan, payload.prompt)
    except AiNotConfigured as exc:
        raise HTTPException(status_code=503, detail={"code": "ai_unconfigured", "message": str(exc)}) from exc
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=502, detail={"code": "ai_provider_error", "message": str(exc)}) from exc


@router.post("/api/gemini/analyze-trades", response_model=AnalyzeTradesResponse)
async def analyze_trades(
    payload: AnalyzeTradesRequest, _user: dict = Depends(require_user)
) -> AnalyzeTradesResponse:
    settings = get_settings()
    if not settings.ai_chat_enabled:
        return AnalyzeTradesResponse(error="AI chat is disabled (AI_CHAT_ENABLED=false)")
    client = _client(settings)
    try:
        if not client.configured:
            if settings.ai_allow_deterministic_fallback:
                return AnalyzeTradesResponse(analysis=deterministic_trade_analysis(payload.trades))
            raise AiNotConfigured("GEMINI_API_KEY is not configured")
        result = await client.generate_text(
            messages=[
                {
                    "role": "user",
                    "content": (
                        "Analyze these paper trades and give concise diagnostics "
                        f"(win rate, risk, next actions):\n{payload.trades}"
                    ),
                }
            ],
            model_selection="flash",
            system="You are a risk-aware paper trading analyst. Be concise.",
        )
        return AnalyzeTradesResponse(analysis=result["reply"])
    except AiNotConfigured as exc:
        return AnalyzeTradesResponse(error=str(exc))
    except Exception as exc:  # noqa: BLE001
        return AnalyzeTradesResponse(error=str(exc))


def _normalize_plan(plan: dict[str, Any], prompt: str) -> dict[str, Any]:
    base = deterministic_plan(prompt)
    directives = plan.get("subAgentDirectives") if isinstance(plan.get("subAgentDirectives"), dict) else {}
    allocation = plan.get("resourceAllocation")
    if not isinstance(allocation, list) or not allocation:
        allocation = base["resourceAllocation"]
    rules = plan.get("suggestedRules")
    if not isinstance(rules, list) or not rules:
        rules = base["suggestedRules"]
    return {
        "planTitle": str(plan.get("planTitle") or base["planTitle"]),
        "summary": str(plan.get("summary") or base["summary"]),
        "subAgentDirectives": {
            "marketData": str(directives.get("marketData") or base["subAgentDirectives"]["marketData"]),
            "adaptiveAgent": str(directives.get("adaptiveAgent") or base["subAgentDirectives"]["adaptiveAgent"]),
            "rnaSmartelligent": str(
                directives.get("rnaSmartelligent") or base["subAgentDirectives"]["rnaSmartelligent"]
            ),
            "riskGovernor": str(directives.get("riskGovernor") or base["subAgentDirectives"]["riskGovernor"]),
        },
        "resourceAllocation": [
            {"name": str(item.get("name")), "value": float(item.get("value", 0))}
            for item in allocation
            if isinstance(item, dict) and item.get("name")
        ],
        "suggestedRules": [str(rule) for rule in rules],
    }
