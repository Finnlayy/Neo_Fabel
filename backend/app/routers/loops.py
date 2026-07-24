"""Runtime paper / live trading loop switches."""

from __future__ import annotations

from typing import Any, Literal

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field, field_validator

from backend.app.auth import require_trading_admin, require_trading_admin_recent
from backend.app.database import SessionFactory
from backend.app.settings import get_settings
from backend.app.trading.live_session_ledger import live_session_ledger, parse_symbol_list
from backend.app.trading.loops import trading_loops
from backend.app.trading.position_sizing import SIZING_MODES
from backend.app.trading.session import Level4Session
from backend.app.trading.trade_approvals import trade_approvals

router = APIRouter(prefix="/api/v1/loops", tags=["loops"])


def _request_id(request: Request) -> str:
    return getattr(request.state, "request_id", None) or request.headers.get("X-Request-ID") or "unknown"


def _level4() -> Level4Session:
    settings = get_settings()
    return Level4Session(settings)


class CapAmountIn(BaseModel):
    value: float = Field(..., ge=0)
    unit: Literal["eur", "usd", "pct"] = "eur"


class LiveStartRequest(BaseModel):
    """Session caps for every live start."""

    max_margin_eur: float | None = Field(
        default=None,
        gt=0,
        description="Legacy alias for max_session_size in EUR",
    )
    max_session_size: CapAmountIn | float | None = Field(
        default=None,
        description="Max session size as {value, unit: eur|usd|pct} or EUR number",
    )
    max_concurrent_trades: int = Field(..., ge=1, le=10)
    starting_capital_eur: float = Field(..., gt=0)
    max_drawdown_usd: float = Field(
        ...,
        gt=0,
        description="Stop live automation when marked session drawdown reaches this USD amount",
    )
    daily_loss_limit: CapAmountIn | float | None = Field(
        default=None,
        description="Daily loss limit {value, unit} — default 5% of capital",
    )
    min_confidence_pct: float = Field(default=0.0, ge=0, le=100)
    allow_pre_post_market: bool = Field(default=True)
    human_verification: bool = Field(
        default=False,
        description="If true, live trades require Telegram approve/reject",
    )
    symbols: list[str] | None = None
    position_sizing_mode: str = Field(...)
    manual_notional_eur: float | None = Field(default=None, gt=0)
    fixed_notional_usd: float | None = Field(default=None, gt=0)

    @field_validator("symbols", mode="before")
    @classmethod
    def _coerce_symbols(cls, value: Any) -> list[str] | None:
        if value is None or value == "":
            return None
        parsed = parse_symbol_list(value if isinstance(value, (str, list)) else str(value))
        return parsed or None

    @field_validator("position_sizing_mode", mode="before")
    @classmethod
    def _normalize_mode(cls, value: Any) -> str:
        return str(value or "").strip().lower()


@router.get("/status")
async def loops_status(_user: dict[str, Any] = Depends(require_trading_admin)) -> dict[str, Any]:
    snap = trading_loops.status(get_settings())
    snap["live"]["sizing_modes"] = list(SIZING_MODES)
    snap["live"]["pending_approvals"] = [p.to_dict() for p in trade_approvals.list_pending()]
    return snap


@router.get("/sessions")
async def list_live_sessions(
    limit: int = 50,
    _user: dict[str, Any] = Depends(require_trading_admin),
) -> dict[str, Any]:
    return {"sessions": live_session_ledger.list_sessions(limit=max(1, min(limit, 200)))}


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
    body: LiveStartRequest,
    _user: dict[str, Any] = Depends(require_trading_admin_recent),
) -> dict[str, Any]:
    rid = _request_id(request)
    size = body.max_session_size
    if size is None and body.max_margin_eur is not None:
        size = body.max_margin_eur
    if size is None:
        raise HTTPException(
            status_code=400,
            detail={
                "code": "session_limits",
                "message": "max_session_size or max_margin_eur required",
                "request_id": rid,
            },
        )
    size_payload: Any = size.model_dump() if isinstance(size, CapAmountIn) else size
    loss_payload: Any = None
    if body.daily_loss_limit is not None:
        loss_payload = (
            body.daily_loss_limit.model_dump()
            if isinstance(body.daily_loss_limit, CapAmountIn)
            else body.daily_loss_limit
        )

    # max_margin_eur arg is only a fallback seed; start_live resolves size via max_session_size.
    margin_seed = float(body.max_margin_eur) if body.max_margin_eur is not None else float(
        body.starting_capital_eur or 10
    )

    result = await trading_loops.start_live(
        get_settings(),
        _level4(),
        max_margin_eur=margin_seed,
        max_concurrent_trades=body.max_concurrent_trades,
        max_drawdown_usd=body.max_drawdown_usd,
        symbols=body.symbols,
        starting_capital_eur=body.starting_capital_eur,
        position_sizing_mode=body.position_sizing_mode,
        manual_notional_eur=body.manual_notional_eur,
        fixed_notional_usd=body.fixed_notional_usd,
        max_session_size=size_payload,
        daily_loss_limit=loss_payload,
        min_confidence_pct=body.min_confidence_pct,
        allow_pre_post_market=body.allow_pre_post_market,
        human_verification=body.human_verification,
    )
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
