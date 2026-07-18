"""TVAPI optimize / chart analyze routes (legacy /api/tvapi paths)."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends

from ..auth import require_user
from ..integrations.gemini_client import AiNotConfigured, GeminiClient
from ..integrations.tvapi_optimizer import run_deterministic_optimize
from ..schemas_ai import TvapiAnalyzeChartRequest, TvapiOptimizeRequest
from ..settings import get_settings

router = APIRouter(tags=["tvapi"])


@router.post("/api/tvapi/optimize")
async def tvapi_optimize(payload: TvapiOptimizeRequest, _user: dict = Depends(require_user)) -> dict[str, Any]:
    settings = get_settings()
    if not settings.tvapi_enabled:
        return {"success": False, "error": "TVAPI is disabled (TVAPI_ENABLED=false)"}
    # RapidAPI external backtest is not wired yet; always return a labeled deterministic sweep.
    # TRADINGVIEW_RAPIDAPI_KEY is reserved for a future verified TV endpoint.
    result = run_deterministic_optimize(payload.model_dump())
    if settings.tradingview_rapidapi_key:
        result["bericht"] += (
            "\n- Note: TRADINGVIEW_RAPIDAPI_KEY is set but external RapidAPI optimize is not "
            "enabled in V1; deterministic-sweep results are returned instead.\n"
        )
    return result


@router.post("/api/tvapi/analyze-chart")
async def tvapi_analyze_chart(
    payload: TvapiAnalyzeChartRequest, _user: dict = Depends(require_user)
) -> dict[str, Any]:
    settings = get_settings()
    if not settings.tvapi_enabled:
        return {"success": False, "error": "TVAPI is disabled (TVAPI_ENABLED=false)"}
    mode = payload.promptMode
    prompt = (
        "Analyze this trading chart for SMC structure, liquidity sweeps, and bias."
        if mode == "pattern"
        else "Review this backtest chart and summarize edge quality, drawdown, and overfitting risk."
    )
    client = GeminiClient(settings)
    try:
        analysis = await client.analyze_image(
            image=payload.image,
            mime_type=payload.mimeType,
            prompt=prompt,
        )
        return {"success": True, "analysis": analysis}
    except AiNotConfigured as exc:
        return {"success": False, "error": str(exc)}
    except Exception as exc:  # noqa: BLE001
        return {"success": False, "error": str(exc)}
