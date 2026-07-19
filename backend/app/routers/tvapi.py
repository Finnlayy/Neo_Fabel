"""TVAPI optimize / chart analyze routes (legacy /api/tvapi paths)."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends

from ..auth import require_user
from ..integrations.gemini_client import AiNotConfigured, GeminiClient
from ..integrations.tvapi_optimizer import list_chart_strategies, run_optimize
from ..schemas_ai import TvapiAnalyzeChartRequest, TvapiChartStrategiesRequest, TvapiOptimizeRequest
from ..settings import get_settings

router = APIRouter(tags=["tvapi"])


@router.post("/api/tvapi/optimize")
async def tvapi_optimize(payload: TvapiOptimizeRequest, _user: dict = Depends(require_user)) -> dict[str, Any]:
    settings = get_settings()
    if not settings.tvapi_enabled:
        return {"success": False, "error": "TVAPI is disabled (TVAPI_ENABLED=false)"}
    # Candle backtest from tv-extension-mvp EMA grid (OHLCV / synthetic). Not vision/YouTube.
    result = await run_optimize(payload.model_dump())
    if settings.tradingview_rapidapi_key and result.get("success"):
        result["bericht"] = str(result.get("bericht") or "") + (
            "\n- Note: TRADINGVIEW_RAPIDAPI_KEY is set but external RapidAPI optimize is not "
            "enabled; candle-backtest results are returned instead.\n"
        )
    return result


@router.post("/api/tvapi/chart-strategies")
async def tvapi_chart_strategies(
    payload: TvapiChartStrategiesRequest, _user: dict = Depends(require_user)
) -> dict[str, Any]:
    settings = get_settings()
    if not settings.tvapi_enabled:
        return {"success": False, "error": "TVAPI is disabled (TVAPI_ENABLED=false)", "strategies": []}
    result = await list_chart_strategies(payload.symbol)
    if not payload.includeProbe and isinstance(result.get("strategies"), list):
        result["strategies"] = [
            s for s in result["strategies"] if isinstance(s, dict) and s.get("origin") != "probe"
        ]
    return result


@router.post("/api/tvapi/analyze-chart")
async def tvapi_analyze_chart(
    payload: TvapiAnalyzeChartRequest, _user: dict = Depends(require_user)
) -> dict[str, Any]:
    settings = get_settings()
    if not settings.tvapi_enabled:
        return {"success": False, "error": "TVAPI is disabled (TVAPI_ENABLED=false)"}
    # Backtest metrics use /api/tvapi/optimize (candle engine). Vision is pattern-only.
    if payload.promptMode == "backtest":
        return {
            "success": False,
            "error": (
                "Backtest Control uses the candle OHLCV engine via POST /api/tvapi/optimize "
                "(tv-extension-mvp). Vision analyze-chart is pattern recognition only; "
                "YouTube/video analysis is disabled."
            ),
        }
    prompt = (
        "You are a BLINDFolded candlestick pattern analyst. "
        "Ignore and do NOT mention ticker/symbol names, exchange labels, timeframes, axis numbers, "
        "dollar/price levels, or numeric indicator values. "
        "Focus ONLY on candle geometry and classic patterns "
        "(Hammer, Inverted Hammer, Hanging Man, Shooting Star, Dragonfly/Gravestone Doji, Doji, "
        "Bullish/Bearish Engulfing, Piercing Line, Dark Cloud Cover, Harami, Inside Bar, "
        "Morning/Evening Star, Three White Soldiers, Three Black Crows, Marubozu, Flags/Wedges as pure shape). "
        "Output: pattern name(s), bias (bullish/bearish/neutral), confidence 0-100, "
        "and one sentence on geometry confluence. No prices. No symbol. No timeframe."
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
