"""Runtime paper / live trading loop switches."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request

from backend.app.auth import require_trading_admin, require_trading_admin_recent
from backend.app.database import SessionFactory
from backend.app.settings import get_settings
from backend.app.trading.loops import trading_loops
from backend.app.trading.session import Level4Session

router = APIRouter(prefix="/api/v1/loops", tags=["loops"])


def _request_id(request: Request) -> str:
    return getattr(request.state, "request_id", None) or request.headers.get("X-Request-ID") or "unknown"


def _level4() -> Level4Session:
    settings = get_settings()
    return Level4Session(settings)


@router.get("/status")
async def loops_status(_user: dict[str, Any] = Depends(require_trading_admin)) -> dict[str, Any]:
    return trading_loops.status(get_settings())


@router.post("/paper/start")
async def paper_loop_start(
    request: Request,
    _user: dict[str, Any] = Depends(require_trading_admin_recent),
) -> dict[str, Any]:
    rid = _request_id(request)
    result = await trading_loops.start_paper(get_settings(), SessionFactory)
    if not result.get("started") and result.get("reason") not in {"ALREADY_RUNNING"}:
        code = str(result.get("reason") or "start_failed").lower()
        raise HTTPException(
            status_code=400 if code != "safety" else 403,
            detail={"code": code, "message": result.get("message") or result.get("reason"), "request_id": rid, **result},
        )
    return {**result, "request_id": rid}


@router.post("/paper/stop")
async def paper_loop_stop(
    request: Request,
    _user: dict[str, Any] = Depends(require_trading_admin_recent),
) -> dict[str, Any]:
    rid = _request_id(request)
    result = await trading_loops.stop_paper()
    return {**result, "request_id": rid}


@router.post("/live/start")
async def live_loop_start(
    request: Request,
    _user: dict[str, Any] = Depends(require_trading_admin_recent),
) -> dict[str, Any]:
    rid = _request_id(request)
    result = await trading_loops.start_live(get_settings(), _level4())
    if not result.get("started"):
        code = str(result.get("reason") or "start_failed").lower()
        status = 403 if code in {"gates", "autonomy_gate"} else 400
        raise HTTPException(
            status_code=status,
            detail={
                "code": code,
                "message": result.get("blocked_reason") or result.get("message") or result.get("reason"),
                "request_id": rid,
                **{k: v for k, v in result.items() if k != "checks"},
                "checks": result.get("checks"),
            },
        )
    return {**result, "request_id": rid}


@router.post("/live/stop")
async def live_loop_stop(
    request: Request,
    _user: dict[str, Any] = Depends(require_trading_admin_recent),
) -> dict[str, Any]:
    rid = _request_id(request)
    result = await trading_loops.stop_live()
    return {**result, "request_id": rid}


@router.post("/kill")
async def trading_kill_switch(
    request: Request,
    _user: dict[str, Any] = Depends(require_trading_admin_recent),
) -> dict[str, Any]:
    """Emergency: stop paper+live loops and cancel-all open orders when trade CLI is enabled."""
    rid = _request_id(request)
    result = await trading_loops.kill_switch(_level4())
    return {**result, "request_id": rid}
