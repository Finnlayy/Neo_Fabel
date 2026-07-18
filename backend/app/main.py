import asyncio
import re
from datetime import UTC, datetime
from typing import Any, Literal, cast
from uuid import uuid4

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.ext.asyncio import AsyncSession

from .auth import require_trading_admin, require_trading_admin_recent, require_user
from .database import get_session
from .integrations.alpha_vantage import AlphaVantageClient, AlphaVantageError
from .integrations.kraken_cli import KrakenCli, KrakenCliError
from .paper_orders import PaperOrderService
from .schemas import MarketBatchItem, MarketBatchResponse, OhlcvBatchResponse, OhlcvItem, PaperOrderRequest, PaperOrderResponse, TickerResponse
from .settings import get_settings
from .routers.ai import router as ai_router
from .routers.telegram import router as telegram_router
from .routers.tvapi import router as tvapi_router
from .signals.mcp_server import mcp_router
from .signals.router import router as signal_router
from .signals.safety import assert_signals_module_imports
from .trading.session import Level4Session


settings = get_settings()
COMMON_SYMBOLS = {
    "crypto": ["BTCUSD", "ETHUSD", "SOLUSD", "XRPUSD", "ADAUSD", "DOGEUSD", "AVAXUSD", "LINKUSD", "DOTUSD", "LTCUSD", "BCHUSD"],
    "forex": ["EURUSD", "GBPUSD", "USDJPY", "USDCHF", "AUDUSD", "USDCAD", "NZDUSD", "EURGBP", "EURJPY", "GBPJPY"],
    "sp500": ["SPY", "VOO", "IVV", "AAPL", "MSFT", "NVDA", "AMZN", "GOOGL", "META", "BRK.B", "TSLA", "AVGO", "JPM", "LLY", "XOM", "UNH", "COST", "WMT", "NFLX", "ORCL", "MA", "HD", "PG", "JNJ", "ABBV", "BAC", "CVX", "KO", "PEP", "AMD", "CRM", "CSCO", "IBM", "CAT", "GE"],
}
SYMBOL_RE = re.compile(r"^[A-Z0-9]+(?:[.-][A-Z0-9]+)?$")
INTRADAY_INTERVALS = {"1min", "5min", "15min", "30min", "60min", "4h"}


def _series_key(payload: dict) -> str | None:
    for key in payload:
        if key.startswith("Time Series") or key.startswith("Crypto Intraday"):
            return key
    return None


def _bars(payload: dict) -> list[dict[str, str]]:
    key = _series_key(payload)
    if key is None or not isinstance(payload.get(key), dict):
        return []
    result: list[dict[str, str]] = []
    for timestamp, values in payload[key].items():
        if not isinstance(values, dict):
            continue
        result.append(
            {
                "timestamp": str(timestamp),
                "open": str(values.get("1. open", "")),
                "high": str(values.get("2. high", "")),
                "low": str(values.get("3. low", "")),
                "close": str(values.get("4. close", "")),
                "volume": str(values.get("5. volume", "")),
            }
        )
    return sorted(result, key=lambda bar: bar["timestamp"])


def _aggregate_four_hour(payload: dict) -> dict:
    from decimal import Decimal, InvalidOperation
    from datetime import datetime

    source = _bars(payload)
    groups: dict[str, list[dict[str, str]]] = {}
    for bar in source:
        try:
            stamp = datetime.fromisoformat(bar["timestamp"].replace(" ", "T"))
            bucket = stamp.replace(hour=(stamp.hour // 4) * 4, minute=0, second=0, microsecond=0).isoformat(sep=" ")
        except ValueError:
            continue
        groups.setdefault(bucket, []).append(bar)

    aggregated: list[dict[str, str]] = []
    for timestamp, bars in sorted(groups.items()):
        try:
            highs = [Decimal(bar["high"]) for bar in bars]
            lows = [Decimal(bar["low"]) for bar in bars]
            volumes = [Decimal(bar["volume"]) for bar in bars if bar["volume"]]
            high = str(max(highs))
            low = str(min(lows))
            volume = str(sum(volumes)) if volumes else ""
        except (InvalidOperation, ValueError):
            continue
        aggregated.append({
            "timestamp": timestamp,
            "open": bars[0]["open"],
            "high": high,
            "low": low,
            "close": bars[-1]["close"],
            "volume": volume,
        })
    return {"bars": aggregated, "source_interval": "60min", "requested_interval": "4h", "aggregated": True}
app = FastAPI(title="Neo Fabel API", version="1.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PATCH"],
    allow_headers=["Authorization", "Content-Type", "Idempotency-Key", "X-Request-ID"],
)
app.include_router(signal_router)
app.include_router(mcp_router)
app.include_router(ai_router)
app.include_router(tvapi_router)
app.include_router(telegram_router)

# Fail import-time if signal modules reference live Kraken execution symbols.
assert_signals_module_imports()


@app.get("/api/v1/auth/me")
async def auth_me(user: dict[str, Any] = Depends(require_user)) -> dict:
    raw_firebase_claims = user.get("firebase")
    firebase_claims: dict[str, Any] = raw_firebase_claims if isinstance(raw_firebase_claims, dict) else {}
    return {
        "uid": str(user["uid"]),
        "email": user.get("email"),
        "display_name": user.get("name"),
        "picture": user.get("picture"),
        "email_verified": user.get("email_verified") is True,
        "provider": firebase_claims.get("sign_in_provider"),
    }


def request_id(request: Request) -> str:
    """Server-generated request ID. Inbound X-Request-ID is not trusted as identity."""
    return str(uuid4())


def kraken() -> KrakenCli:
    return KrakenCli(
        binary=settings.kraken_binary,
        timeout_seconds=settings.kraken_timeout_seconds,
        allow_trade_commands=settings.trade_commands_enabled,
    )


def level4_session() -> Level4Session:
    return Level4Session(settings, cli=kraken())


def alpha_vantage() -> AlphaVantageClient:
    return AlphaVantageClient(
        api_key=settings.alphavantage_api_key,
        base_url=settings.alphavantage_base_url,
        timeout_seconds=settings.alphavantage_timeout_seconds,
    )


@app.get("/health/live")
async def health_live() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/health/ready")
async def health_ready() -> dict[str, str | int | bool]:
    execution = "live-autonomous" if settings.trade_commands_enabled and settings.autonomy.value >= 4 else "paper-only"
    return {
        "status": "ok",
        "database": "pending-migration",
        "execution": execution,
        "autonomy_level": int(settings.autonomy),
        "live_trading_enabled": settings.kraken_live_trading_enabled,
    }


@app.get("/api/v1/trading/autonomy")
async def trading_autonomy() -> dict:
    guardrails = settings.trading_guardrails()
    return {
        "autonomy_level": int(settings.autonomy),
        "live_trading_enabled": settings.kraken_live_trading_enabled,
        "trade_commands_enabled": settings.trade_commands_enabled,
        "deadman_seconds": settings.kraken_deadman_seconds,
        "guardrails": {
            "max_order_size": str(guardrails.max_order_size),
            "max_open_positions": guardrails.max_open_positions,
            "max_trades_per_hour": guardrails.max_trades_per_hour,
            "pair_allowlist": sorted(guardrails.pair_allowlist),
        },
        "required_for_level4": [
            "KRAKEN_AUTONOMY_LEVEL=4",
            "KRAKEN_LIVE_TRADING_ENABLED=true",
            "trade-only API key (no Withdraw Funds)",
            "dead man's switch armed each session",
        ],
    }


@app.get("/api/v1/trading/preflight")
async def trading_preflight(request: Request, _user: dict = Depends(require_trading_admin)) -> dict:
    rid = request_id(request)
    result = await level4_session().preflight()
    return {
        "ok": result.ok,
        "checks": result.checks,
        "autonomy_level": result.autonomy_level,
        "live_trading_enabled": result.live_trading_enabled,
        "request_id": rid,
    }


@app.get("/api/v1/trading/monitor")
async def trading_monitor(request: Request, _user: dict = Depends(require_trading_admin)) -> dict:
    """Level 1 monitor snapshot (balances + open orders + guardrail state)."""
    rid = request_id(request)
    snapshot = await level4_session().monitor_snapshot()
    return {**snapshot, "request_id": rid}


@app.post("/api/v1/trading/deadman")
async def trading_deadman(request: Request, _user: dict = Depends(require_trading_admin_recent)) -> dict:
    """Arm or refresh the dead man's switch (requires Level 4 + live flag)."""
    rid = request_id(request)
    try:
        result = await level4_session().arm_deadman()
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail={"code": "autonomy_gate", "message": str(exc), "request_id": rid}) from exc
    except KrakenCliError as exc:
        status = 503 if exc.retryable else 422
        raise HTTPException(status_code=status, detail={"code": exc.category, "message": str(exc), "request_id": rid}) from exc
    return {"deadman": result, "seconds": settings.kraken_deadman_seconds, "request_id": rid}


@app.get("/api/v1/market/ticker/{pair}", response_model=TickerResponse)
async def ticker(pair: str, request: Request) -> TickerResponse:
    rid = request_id(request)
    try:
        result = await kraken().ticker(pair)
    except KrakenCliError as exc:
        raise HTTPException(status_code=503, detail={"code": exc.category, "message": str(exc), "request_id": rid}) from exc
    return TickerResponse(pair=pair.upper(), data=result, as_of=datetime.now(UTC).isoformat(), request_id=rid)


def _batch_symbols(asset_class: str, symbols: str | None) -> dict[str, list[str]]:
    classes = ["crypto", "forex", "sp500"] if asset_class == "all" else [asset_class]
    if symbols:
        requested = [value.strip().upper() for value in symbols.split(",") if value.strip()]
        if not requested or len(requested) > 100 or any(not SYMBOL_RE.fullmatch(value) for value in requested):
            raise HTTPException(status_code=422, detail={"code": "invalid_symbols", "message": "symbols must be 1-100 comma-separated safe symbols"})
        return {classes[0]: requested} if len(classes) == 1 else {"sp500": requested}
    return {name: COMMON_SYMBOLS[name] for name in classes}


@app.get("/api/v1/market/batch", response_model=MarketBatchResponse)
async def market_batch(
    request: Request,
    asset_class: str = "all",
    symbols: str | None = None,
) -> MarketBatchResponse:
    rid = request_id(request)
    if asset_class not in {"all", "crypto", "forex", "sp500"}:
        raise HTTPException(status_code=422, detail={"code": "invalid_asset_class", "message": "asset_class must be all, crypto, forex, or sp500"})
    symbol_groups = _batch_symbols(asset_class, symbols)
    items: list[MarketBatchItem] = []

    async def crypto_item(symbol: str) -> MarketBatchItem:
        try:
            return MarketBatchItem(symbol=symbol, asset_class="crypto", status="ok", source="kraken-cli", data=await kraken().ticker(symbol))
        except KrakenCliError as exc:
            return MarketBatchItem(symbol=symbol, asset_class="crypto", status="error", source="kraken-cli", error={"code": exc.category, "message": str(exc)})

    crypto_items = await asyncio.gather(*(crypto_item(symbol) for symbol in symbol_groups.get("crypto", [])))
    items.extend(crypto_items)

    av = alpha_vantage()
    for symbol, result in await av.forex_batch(symbol_groups.get("forex", []), settings.alphavantage_batch_concurrency):
        if isinstance(result, Exception):
            category = result.category if isinstance(result, AlphaVantageError) else "provider"
            items.append(MarketBatchItem(symbol=symbol, asset_class="forex", status="error", source="alpha-vantage", error={"code": category, "message": str(result)}))
        else:
            items.append(MarketBatchItem(symbol=symbol, asset_class="forex", status="ok", source="alpha-vantage", data=result))

    equities = symbol_groups.get("sp500", [])
    if equities:
        try:
            if not settings.alphavantage_bulk_quotes_enabled:
                raise AlphaVantageError("config", "ALPHAVANTAGE_BULK_QUOTES_ENABLED must be true for the full equity batch")
            result = await av.equity_bulk(equities)
            for symbol in equities:
                items.append(MarketBatchItem(symbol=symbol, asset_class="sp500", status="ok", source="alpha-vantage", data=result))
        except AlphaVantageError as exc:
            for symbol in equities:
                items.append(MarketBatchItem(symbol=symbol, asset_class="sp500", status="error", source="alpha-vantage", error={"code": exc.category, "message": str(exc)}))

    return MarketBatchResponse(
        requested=len(items),
        succeeded=sum(item.status == "ok" for item in items),
        failed=sum(item.status == "error" for item in items),
        as_of=datetime.now(UTC).isoformat(),
        request_id=rid,
        items=items,
    )


@app.get("/api/v1/market/ohlcv", response_model=OhlcvBatchResponse)
async def market_ohlcv(
    request: Request,
    asset_class: str = "sp500",
    symbols: str | None = None,
    intervals: str = "1min,5min,15min,60min,4h",
) -> OhlcvBatchResponse:
    rid = request_id(request)
    if asset_class not in {"crypto", "forex", "sp500"}:
        raise HTTPException(status_code=422, detail={"code": "invalid_asset_class", "message": "asset_class must be crypto, forex, or sp500"})
    asset_class_name = cast(Literal["crypto", "forex", "sp500"], asset_class)
    requested_intervals = [value.strip().lower() for value in intervals.split(",") if value.strip()]
    if not requested_intervals or len(requested_intervals) > 5 or any(value not in INTRADAY_INTERVALS for value in requested_intervals):
        raise HTTPException(status_code=422, detail={"code": "invalid_intervals", "message": "intervals must be selected from 1min, 5min, 15min, 30min, 60min, 4h"})
    groups = _batch_symbols(asset_class_name, symbols)
    symbol_list = groups[asset_class_name]
    if len(symbol_list) * len(requested_intervals) > 100:
        raise HTTPException(status_code=422, detail={"code": "batch_too_large", "message": "at most 100 symbol/interval requests are allowed per call"})

    av = alpha_vantage()
    items: list[OhlcvItem] = []
    semaphore = asyncio.Semaphore(max(1, settings.alphavantage_batch_concurrency))

    async def fetch(symbol: str, interval: str) -> OhlcvItem:
        async with semaphore:
            try:
                source_interval = "60min" if interval == "4h" else interval
                payload = await av.intraday(asset_class_name, symbol, source_interval)
                data = _aggregate_four_hour(payload) if interval == "4h" else {"bars": _bars(payload), "requested_interval": interval}
                return OhlcvItem(symbol=symbol, asset_class=asset_class_name, interval=interval, status="ok", source="alpha-vantage", data=data)
            except AlphaVantageError as exc:
                return OhlcvItem(symbol=symbol, asset_class=asset_class_name, interval=interval, status="error", source="alpha-vantage", error={"code": exc.category, "message": str(exc)})

    items.extend(await asyncio.gather(*(fetch(symbol, interval) for symbol in symbol_list for interval in requested_intervals)))
    return OhlcvBatchResponse(
        requested=len(items),
        succeeded=sum(item.status == "ok" for item in items),
        failed=sum(item.status == "error" for item in items),
        as_of=datetime.now(UTC).isoformat(),
        request_id=rid,
        items=items,
    )


@app.get("/api/v1/paper/status")
async def paper_status(request: Request, _user: dict = Depends(require_user)) -> dict:
    rid = request_id(request)
    try:
        return {"mode": "paper", "data": await kraken().paper_status(), "request_id": rid}
    except KrakenCliError as exc:
        raise HTTPException(status_code=503, detail={"code": exc.category, "message": str(exc), "request_id": rid}) from exc


@app.post("/api/v1/paper/orders", response_model=PaperOrderResponse)
async def paper_order(
    payload: PaperOrderRequest,
    request: Request,
    user: dict = Depends(require_user),
    session: AsyncSession = Depends(get_session),
) -> PaperOrderResponse:
    rid = request_id(request)
    service = PaperOrderService(sink=kraken())
    return await service.place_manual(
        session=session,
        user_uid=str(user.get("uid", "")),
        payload=payload,
        request_id=rid,
    )
