"""Trade Agent HTTP surface — status, start/stop, manual job triggers."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request

from backend.app.auth import require_trading_admin, require_trading_admin_recent
from backend.app.settings import get_settings
from backend.app.trading.trade_agent.runtime import trade_agent

router = APIRouter(prefix="/api/v1/trade-agent", tags=["trade-agent"])


def _rid(request: Request) -> str:
    return getattr(request.state, "request_id", None) or request.headers.get("X-Request-ID") or "unknown"


@router.get("/status")
async def trade_agent_status(_user: dict[str, Any] = Depends(require_trading_admin)) -> dict[str, Any]:
    settings = get_settings()
    return {
        "enabled": settings.trade_agent_enabled,
        "auto_start": settings.trade_agent_auto_start,
        **trade_agent.status(),
    }


@router.post("/start")
async def trade_agent_start(
    request: Request,
    _user: dict[str, Any] = Depends(require_trading_admin_recent),
) -> dict[str, Any]:
    rid = _rid(request)
    result = await trade_agent.start(get_settings())
    if not result.get("started") and result.get("reason") not in {"ALREADY_RUNNING"}:
        raise HTTPException(
            status_code=400,
            detail={"code": str(result.get("reason") or "start_failed").lower(), "message": result, "request_id": rid},
        )
    return {**result, "request_id": rid}


@router.post("/stop")
async def trade_agent_stop(
    request: Request,
    _user: dict[str, Any] = Depends(require_trading_admin_recent),
) -> dict[str, Any]:
    return {**(await trade_agent.stop()), "request_id": _rid(request)}


@router.post("/feedback/run")
async def trade_agent_feedback_run(
    request: Request,
    _user: dict[str, Any] = Depends(require_trading_admin_recent),
) -> dict[str, Any]:
    from backend.app.trading.feedback import feedback_engine

    result = await feedback_engine.run_cycle(reason="api", force=True)
    return {**result, "request_id": _rid(request)}


@router.get("/feedback/status")
async def trade_agent_feedback_status(
    _user: dict[str, Any] = Depends(require_trading_admin),
) -> dict[str, Any]:
    from backend.app.trading.feedback import feedback_engine

    settings = get_settings()
    return {
        "enabled": settings.feedback_engine_enabled,
        "gate": feedback_engine.is_idle_or_paper_quiet(settings),
        "last_run": feedback_engine.last_run,
    }


@router.post("/trigger/{job_id}")
async def trade_agent_trigger(
    job_id: str,
    request: Request,
    _user: dict[str, Any] = Depends(require_trading_admin_recent),
) -> dict[str, Any]:
    allowed = {
        "market_scan",
        "market_scan_morning",
        "market_scan_preopen",
        "market_scan_hours",
        "label_trades",
        "feedback_idle",
        "optimizer_night",
        "check_status",
        "check_positions",
        "et_gap_momentum",
        "et_post_open",
        "et_midday",
        "et_afternoon",
        "et_power_hour",
    }
    if job_id not in allowed:
        raise HTTPException(status_code=404, detail={"code": "unknown_job", "message": job_id})
    result = await trade_agent.trigger(job_id, reason="api")
    return {**result, "request_id": _rid(request)}
