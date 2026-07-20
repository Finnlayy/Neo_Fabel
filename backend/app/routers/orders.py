"""Manual order desk — paper + gated live Kraken order surface."""

from __future__ import annotations

from decimal import Decimal
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request

from backend.app.auth import require_trading_admin, require_trading_admin_recent
from backend.app.database import SessionFactory
from backend.app.integrations.kraken_cli import KrakenCli, KrakenCliError
from backend.app.integrations.kraken_status import assert_safe_to_trade_pair
from backend.app.integrations.paper_factory import build_paper_router
from backend.app.paper_orders import PaperOrderService
from backend.app.schemas import (
    AmendOrderRequest,
    CancelAllOrdersRequest,
    CancelOrderRequest,
    PaperOrderRequest,
    PlaceOrderRequest,
    PlaceOrderResponse,
)
from backend.app.settings import get_settings, get_trade_rate_limiter
from backend.app.trading.autonomy import AutonomyLevel, require_autonomy
from backend.app.trading.capital_policy import assert_live_order_capital, assert_no_debt_leverage
from backend.app.trading.guardrails import GuardrailViolation

router = APIRouter(prefix="/api/v1/orders", tags=["orders"])


def _request_id(request: Request) -> str:
    return getattr(request.state, "request_id", None) or request.headers.get("X-Request-ID") or "unknown"


def _cli() -> KrakenCli:
    settings = get_settings()
    return KrakenCli(
        binary=settings.kraken_binary,
        timeout_seconds=settings.kraken_timeout_seconds,
        allow_trade_commands=settings.trade_commands_enabled,
    )


def _assert_live_manual() -> None:
    settings = get_settings()
    if not settings.kraken_live_trading_enabled:
        raise PermissionError("KRAKEN_LIVE_TRADING_ENABLED must be true for live orders")
    require_autonomy(settings.autonomy, AutonomyLevel.SUPERVISED)


def _as_decimal(value: Decimal | str | None) -> Decimal | None:
    if value is None:
        return None
    if isinstance(value, Decimal):
        return value
    return Decimal(str(value))


async def _place_paper(payload: PlaceOrderRequest, user: dict[str, Any], rid: str) -> PlaceOrderResponse:
    if payload.order_type not in {"market", "limit"}:
        raise HTTPException(
            status_code=422,
            detail={"code": "paper_order_type", "message": "paper supports market/limit only", "request_id": rid},
        )
    price = _as_decimal(payload.price) if payload.price is not None else None
    paper_req = PaperOrderRequest(
        pair=payload.pair,
        side=payload.side,
        volume=payload.volume,
        order_type=payload.order_type,  # type: ignore[arg-type]
        price=price,
        market_type=payload.market_type,
        leverage=payload.leverage,
        idempotency_key=payload.idempotency_key,
    )
    sink = build_paper_router(get_settings())
    try:
        async with SessionFactory() as session:
            service = PaperOrderService(sink=sink)
            result = await service.place_manual(
                session=session,
                user_uid=str(user.get("uid") or user.get("sub") or ""),
                payload=paper_req,
                request_id=rid,
            )
            return PlaceOrderResponse(
                idempotency_key=result.idempotency_key,
                mode="paper",
                status=result.status,
                result=result.result,
                request_id=rid,
            )
    except HTTPException as exc:
        detail = exc.detail if isinstance(exc.detail, dict) else {}
        if exc.status_code != 503 or detail.get("code") != "database_unavailable":
            raise
    except Exception:
        pass

    try:
        raw = await sink.paper_order(
            paper_req.side,
            paper_req.pair,
            paper_req.volume,
            paper_req.order_type,
            paper_req.price,
            market_type=paper_req.market_type,
            leverage=paper_req.leverage,
        )
    except (KrakenCliError, ValueError) as sink_exc:
        raise HTTPException(
            status_code=503,
            detail={"code": "paper_unavailable", "message": str(sink_exc), "request_id": rid},
        ) from sink_exc
    return PlaceOrderResponse(
        idempotency_key=payload.idempotency_key,
        mode="paper",
        status="ACCEPTED",
        result=raw if isinstance(raw, dict) else {"raw": raw},
        request_id=rid,
    )


@router.post("", response_model=PlaceOrderResponse)
async def place_order(
    payload: PlaceOrderRequest,
    request: Request,
    user: dict[str, Any] = Depends(require_trading_admin_recent),
) -> PlaceOrderResponse:
    rid = _request_id(request)
    if payload.mode == "paper":
        return await _place_paper(payload, user, rid)

    try:
        _assert_live_manual()
    except PermissionError as exc:
        raise HTTPException(
            status_code=403,
            detail={"code": "autonomy_gate", "message": str(exc), "request_id": rid},
        ) from exc

    cli = _cli()
    price: Decimal | str | None = payload.price
    price2: Decimal | str | None = payload.price2
    limiter = get_trade_rate_limiter()
    if not payload.validate_only:
        try:
            limiter.assert_can_trade()
        except GuardrailViolation as exc:
            raise HTTPException(
                status_code=429,
                detail={"code": exc.code, "message": str(exc), "request_id": rid},
            ) from exc

    try:
        assert_no_debt_leverage(
            leverage=payload.leverage,
            market_type=payload.market_type,
            reduce_only=payload.reduce_only,
        )
        assert_safe_to_trade_pair(payload.pair)
    except GuardrailViolation as exc:
        raise HTTPException(
            status_code=403,
            detail={"code": exc.code, "message": str(exc), "request_id": rid},
        ) from exc

    if isinstance(price, Decimal):
        price_dec: Decimal | None = price
    elif isinstance(price, str) and price.strip() and not price.strip().startswith("+"):
        price_dec = _as_decimal(price)
    else:
        price_dec = None

    if not payload.validate_only:
        try:
            balance = await cli.balance()
            est_price = price_dec
            if est_price is None and payload.side == "buy":
                try:
                    tick = await cli.ticker(payload.pair)
                    last = tick.get("last") or tick.get("price") or tick.get("close")
                    if isinstance(last, list) and last:
                        last = last[0]
                    est_price = _as_decimal(last)
                except KrakenCliError:
                    est_price = None
            assert_live_order_capital(
                side=payload.side,
                pair=payload.pair,
                volume=payload.volume,
                price=est_price,
                balance_payload=balance if isinstance(balance, dict) else None,
                market_type=payload.market_type,
                leverage=payload.leverage,
                reduce_only=payload.reduce_only,
                max_notional=get_settings().kraken_max_notional,
            )
        except GuardrailViolation as exc:
            from backend.app.trading.live_audit import log_live_event

            log_live_event(
                "live_reject",
                code=exc.code,
                message=str(exc),
                side=payload.side,
                pair=payload.pair,
                volume=str(payload.volume),
                source="orders_api",
            )
            raise HTTPException(
                status_code=403,
                detail={"code": exc.code, "message": str(exc), "request_id": rid},
            ) from exc
        except KrakenCliError as exc:
            raise HTTPException(
                status_code=503 if exc.retryable else 422,
                detail={"code": exc.category, "message": str(exc), "request_id": rid},
            ) from exc

    try:
        if payload.market_type == "futures":
            if payload.validate_only:
                raise HTTPException(
                    status_code=422,
                    detail={
                        "code": "validate_unsupported",
                        "message": "futures validate_only not supported",
                        "request_id": rid,
                    },
                )
            raw = await cli.futures_place_order(
                payload.side,
                payload.pair,
                payload.volume,
                order_type=payload.order_type,
                price=_as_decimal(price) if not isinstance(price, str) else _as_decimal(price),
                stop_price=_as_decimal(price2),
                reduce_only=True,
                yes=True,
            )
        elif payload.validate_only:
            raw = await cli.validate_order(
                payload.side,
                payload.pair,
                payload.volume,
                payload.order_type,
                price,
                price2=price2,
                time_in_force=payload.time_in_force,
            )
        else:
            raw = await cli.place_order(
                payload.side,
                payload.pair,
                payload.volume,
                payload.order_type,
                price,
                price2=price2,
                time_in_force=payload.time_in_force,
                yes=True,
            )
    except KrakenCliError as exc:
        status = 503 if exc.retryable else 422
        raise HTTPException(
            status_code=status,
            detail={"code": exc.category, "message": str(exc), "request_id": rid},
        ) from exc

    if not payload.validate_only:
        limiter.record_trade()
        from backend.app.trading.live_audit import log_live_event

        log_live_event(
            "live_place",
            side=payload.side,
            pair=payload.pair,
            volume=str(payload.volume),
            order_type=payload.order_type,
            mode="live",
            source="orders_api",
            request_id=rid,
        )

    return PlaceOrderResponse(
        idempotency_key=payload.idempotency_key,
        mode="live",
        status="VALIDATED" if payload.validate_only else "ACCEPTED",
        result=raw,
        request_id=rid,
    )


@router.post("/cancel")
async def cancel_order(
    payload: CancelOrderRequest,
    request: Request,
    _user: dict[str, Any] = Depends(require_trading_admin_recent),
) -> dict[str, Any]:
    rid = _request_id(request)
    if payload.mode == "paper":
        cli = _cli()
        try:
            raw = await cli.paper_cancel(payload.order_id)
        except KrakenCliError as exc:
            raise HTTPException(
                status_code=422,
                detail={"code": exc.category, "message": str(exc), "request_id": rid},
            ) from exc
        return {"mode": "paper", "result": raw, "request_id": rid}

    try:
        _assert_live_manual()
    except PermissionError as exc:
        raise HTTPException(
            status_code=403, detail={"code": "autonomy_gate", "message": str(exc), "request_id": rid}
        ) from exc

    cli = _cli()
    try:
        if payload.market_type == "futures":
            raw = await cli.futures_cancel(payload.order_id)
        else:
            raw = await cli.cancel_order(payload.order_id)
    except KrakenCliError as exc:
        status = 503 if exc.retryable else 422
        raise HTTPException(
            status_code=status, detail={"code": exc.category, "message": str(exc), "request_id": rid}
        ) from exc
    return {"mode": "live", "result": raw, "request_id": rid}


@router.post("/cancel-all")
async def cancel_all_orders(
    payload: CancelAllOrdersRequest,
    request: Request,
    _user: dict[str, Any] = Depends(require_trading_admin_recent),
) -> dict[str, Any]:
    rid = _request_id(request)
    if not payload.confirm:
        raise HTTPException(
            status_code=400,
            detail={"code": "confirm_required", "message": "confirm=true required for cancel-all", "request_id": rid},
        )
    if payload.mode == "paper":
        raise HTTPException(
            status_code=422,
            detail={
                "code": "paper_cancel_all",
                "message": "paper cancel-all not supported via Kraken CLI path",
                "request_id": rid,
            },
        )
    try:
        _assert_live_manual()
    except PermissionError as exc:
        raise HTTPException(
            status_code=403, detail={"code": "autonomy_gate", "message": str(exc), "request_id": rid}
        ) from exc

    cli = _cli()
    try:
        if payload.market_type == "futures":
            raw = await cli.futures_cancel_all(symbol=payload.symbol)
        else:
            raw = await cli.cancel_all()
    except KrakenCliError as exc:
        status = 503 if exc.retryable else 422
        raise HTTPException(
            status_code=status, detail={"code": exc.category, "message": str(exc), "request_id": rid}
        ) from exc
    return {"mode": "live", "result": raw, "request_id": rid}


@router.post("/amend")
async def amend_order(
    payload: AmendOrderRequest,
    request: Request,
    _user: dict[str, Any] = Depends(require_trading_admin_recent),
) -> dict[str, Any]:
    rid = _request_id(request)
    if payload.mode == "paper":
        raise HTTPException(
            status_code=422,
            detail={"code": "paper_amend", "message": "amend paper orders via cancel + new order", "request_id": rid},
        )
    try:
        _assert_live_manual()
    except PermissionError as exc:
        raise HTTPException(
            status_code=403, detail={"code": "autonomy_gate", "message": str(exc), "request_id": rid}
        ) from exc

    cli = _cli()
    try:
        if payload.market_type == "futures":
            raw = await cli.futures_edit_order(payload.order_id, price=payload.price, volume=payload.volume)
            return {"mode": "live", "action": "edit", "result": raw, "request_id": rid}
        try:
            raw = await cli.amend_order(payload.order_id, price=payload.price, volume=payload.volume)
            return {"mode": "live", "action": "amend", "result": raw, "request_id": rid}
        except KrakenCliError as amend_exc:
            if not payload.replace_on_amend_fail:
                raise
            if not payload.pair or not payload.side or not payload.order_type or payload.volume is None:
                raise HTTPException(
                    status_code=422,
                    detail={
                        "code": "replace_fields_required",
                        "message": f"amend failed ({amend_exc}); provide pair/side/order_type/volume to cancel+replace",
                        "request_id": rid,
                    },
                ) from amend_exc
            await cli.cancel_order(payload.order_id)
            raw = await cli.place_order(
                payload.side,
                payload.pair,
                payload.volume,
                payload.order_type,
                payload.price,
                yes=True,
            )
            return {"mode": "live", "action": "cancel_replace", "result": raw, "request_id": rid}
    except HTTPException:
        raise
    except KrakenCliError as exc:
        status = 503 if exc.retryable else 422
        raise HTTPException(
            status_code=status, detail={"code": exc.category, "message": str(exc), "request_id": rid}
        ) from exc


@router.get("/types")
async def order_types(_user: dict[str, Any] = Depends(require_trading_admin)) -> dict[str, Any]:
    return {
        "spot": [
            "market",
            "limit",
            "stop-loss",
            "stop-loss-limit",
            "take-profit",
            "take-profit-limit",
            "trailing-stop",
            "trailing-stop-limit",
        ],
        "futures": ["market", "limit", "stop"],
        "paper": ["market", "limit"],
        "time_in_force": ["GTC", "IOC", "GTD", "FOK"],
    }
