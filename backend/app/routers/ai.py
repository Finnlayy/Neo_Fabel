"""AI chat, orchestrate, and trade-analysis routes (legacy /api paths)."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException

from ..academy.prompt_shot_log import append_prompt_shot_event
from ..ai_prompts.loader import build_orchestrator_system, classify_skill_gate, skill_names_in_text
from ..auth import require_user
from ..integrations.chat_context import trim_chat_messages
from ..integrations.gemini_client import (
    AiNotConfigured,
    deterministic_plan,
    deterministic_trade_analysis,
)
from ..integrations.llm_router import LlmRouter
from ..integrations.opencode_config import build_opencode_config
from ..schemas_ai import (
    AnalyzeTradesRequest,
    AnalyzeTradesResponse,
    ChatContextMeta,
    ChatRequest,
    ChatResponse,
    OrchestrateRequest,
)
from ..settings import Settings, get_settings

router = APIRouter(tags=["ai"])

_DIRECTIVE_KEYS = (
    "marketData",
    "adaptiveAgent",
    "rnaSmartelligent",
    "riskGovernor",
    "krakenBroker",
    "predictive",
    "analytic",
    "orchestrator",
)


def _client(settings: Settings | None = None) -> LlmRouter:
    return LlmRouter(settings or get_settings())


def _packets_blob(packets: list[Any]) -> str:
    if not packets:
        return ""
    lines: list[str] = []
    for packet in packets[:16]:
        data = packet.model_dump() if hasattr(packet, "model_dump") else dict(packet)
        lines.append(
            "{"
            f"id={data.get('id')}, status={data.get('status')}, "
            f"lastAction={str(data.get('lastAction') or '')[:200]}, "
            f"directive={str(data.get('directive') or '')[:280]}"
            "}"
        )
    return "AGENT STATUS PACKETS:\n" + "\n".join(lines)


def _skill_routing_ok(text: str) -> bool:
    """False if any live_gated skill is framed as DELEGATE/PROCEED."""
    upper = (text or "").upper()
    for skill in skill_names_in_text(text):
        if classify_skill_gate(skill) != "live_gated":
            continue
        # Live skills named alongside refuse/block are OK.
        window = text.lower()
        if "refuse" in window or "block" in window or "live_gated" in window:
            continue
        if any(tok in upper for tok in ("DELEGATE", "PROCEED", "EXECUTE", "WITHDRAW")):
            return False
    return True


@router.get("/api/ai/health")
async def ai_health() -> dict[str, Any]:
    return _client().status_payload()


@router.get("/api/ai/opencode-config")
async def ai_opencode_config(
    _user: dict = Depends(require_user),
    settings: Settings = Depends(get_settings),
) -> dict[str, Any]:
    """OpenCode provider schema for local tooling; apiKey only in development."""
    include_key = settings.app_env == "development" and bool(settings.aiprimetech_api_key)
    return build_opencode_config(settings, include_api_key=include_key)


@router.post("/api/chat", response_model=ChatResponse)
async def chat(payload: ChatRequest, _user: dict = Depends(require_user)) -> ChatResponse:
    settings = get_settings()
    if not settings.ai_chat_enabled:
        return ChatResponse(success=False, error="AI chat is disabled (AI_CHAT_ENABLED=false)")
    client = _client(settings)
    wire_messages, trim_meta = trim_chat_messages(
        [m.model_dump() for m in payload.messages],
        max_messages=settings.ai_chat_max_messages,
        max_chars=settings.ai_chat_max_chars,
        max_content_chars=settings.ai_chat_max_content_chars,
    )

    shot_ids: list[str] = []
    if payload.mode == "orchestrator":
        system, shot_ids = build_orchestrator_system(channel="chat-orch")
        blob = _packets_blob(payload.agentStatusPackets)
        if blob:
            # Packets go into systemInstruction — not unbounded history.
            system = f"{system}\n\n{blob}"[:6_000]
    else:
        system = (
            "You are Neo Fabel's paper-trading assistant. Prefer Pine Script v5, "
            "risk controls, and paper-only execution guidance. Never instruct live order placement. "
            "Keep replies concise unless the user explicitly asks for full code."
        )

    try:
        result = await client.generate_text(
            messages=wire_messages,
            model_selection=payload.modelSelection,
            system=system,
        )
        reply = result["reply"]
        if payload.mode == "orchestrator":
            append_prompt_shot_event(
                {
                    "channel": "chat-orch",
                    "shot_ids": shot_ids,
                    "prompt_version_id": "orchestrator_runtime",
                    "roster": [p.model_dump() for p in payload.agentStatusPackets],
                    "skill_hints": skill_names_in_text(reply or ""),
                    "skill_routing_ok": _skill_routing_ok(reply or ""),
                    "outcome": "PROCEED",
                }
            )
        return ChatResponse(
            success=True,
            reply=reply,
            modelUsed=result["modelUsed"],
            routeLabel=result["routeLabel"],
            provider=result.get("provider"),
            citations=result.get("citations") or [],
            context=ChatContextMeta(**trim_meta),
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
    system, shot_ids = build_orchestrator_system(channel="orchestrate")
    blob = _packets_blob(payload.agentStatusPackets)
    prompt = payload.prompt
    if blob:
        prompt = f"{payload.prompt}\n\n{blob}"

    try:
        if not client.configured:
            if settings.ai_allow_deterministic_fallback:
                plan = deterministic_plan(payload.prompt)
                _log_orchestrate(plan, shot_ids, payload)
                return plan
            raise AiNotConfigured(
                "No LLM provider configured (GEMINI_API_KEY / OPENROUTER_API_KEY / GROQ_API_KEY)"
            )
        plan = await client.generate_json(prompt=prompt, system=system, model_selection="flash")
        normalized = _normalize_plan(plan, payload.prompt)
        _log_orchestrate(normalized, shot_ids, payload)
        return normalized
    except AiNotConfigured as exc:
        raise HTTPException(status_code=503, detail={"code": "ai_unconfigured", "message": str(exc)}) from exc
    except Exception as exc:
        raise HTTPException(status_code=502, detail={"code": "ai_provider_error", "message": str(exc)}) from exc


def _log_orchestrate(plan: dict[str, Any], shot_ids: list[str], payload: OrchestrateRequest) -> None:
    raw_directives = plan.get("subAgentDirectives")
    directives: dict[str, Any] = raw_directives if isinstance(raw_directives, dict) else {}
    joined = " ".join(str(v) for v in directives.values())
    append_prompt_shot_event(
        {
            "channel": "orchestrate",
            "shot_ids": shot_ids,
            "prompt_version_id": "orchestrator_runtime",
            "roster": [p.model_dump() for p in payload.agentStatusPackets],
            "emitted_directives": {k: str(directives.get(k, ""))[:280] for k in _DIRECTIVE_KEYS},
            "skill_hints": skill_names_in_text(joined),
            "skill_routing_ok": _skill_routing_ok(joined),
            "outcome": "HANDOFF",
        }
    )


@router.post("/api/gemini/analyze-trades", response_model=AnalyzeTradesResponse)
async def analyze_trades(
    payload: AnalyzeTradesRequest, _user: dict = Depends(require_user)
) -> AnalyzeTradesResponse:
    settings = get_settings()
    if not settings.ai_chat_enabled:
        return AnalyzeTradesResponse(error="AI chat is disabled (AI_CHAT_ENABLED=false)")
    client = _client(settings)
    trades = payload.trades or []
    sample = trades[-25:]
    try:
        if not client.configured:
            if settings.ai_allow_deterministic_fallback:
                return AnalyzeTradesResponse(analysis=deterministic_trade_analysis(sample))
            raise AiNotConfigured(
                "No LLM provider configured (GEMINI_API_KEY / OPENROUTER_API_KEY / GROQ_API_KEY)"
            )
        result = await client.generate_text(
            messages=[
                {
                    "role": "user",
                    "content": (
                        "Analyze these paper trades and give concise diagnostics "
                        f"(win rate, risk, next actions). Showing last {len(sample)} of {len(trades)}:\n"
                        f"{sample}"
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
    raw_directives = plan.get("subAgentDirectives")
    directives: dict[str, Any] = raw_directives if isinstance(raw_directives, dict) else {}
    allocation = plan.get("resourceAllocation")
    if not isinstance(allocation, list) or not allocation:
        allocation = base["resourceAllocation"]
    rules = plan.get("suggestedRules")
    if not isinstance(rules, list) or not rules:
        rules = base["suggestedRules"]
    base_dirs = base["subAgentDirectives"]
    return {
        "planTitle": str(plan.get("planTitle") or base["planTitle"]),
        "summary": str(plan.get("summary") or base["summary"]),
        "subAgentDirectives": {
            key: str(directives.get(key) or base_dirs[key])[:500] for key in _DIRECTIVE_KEYS
        },
        "resourceAllocation": [
            {"name": str(item.get("name")), "value": float(item.get("value", 0))}
            for item in allocation
            if isinstance(item, dict) and item.get("name")
        ],
        "suggestedRules": [str(rule) for rule in rules],
    }
