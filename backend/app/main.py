import asyncio
import logging
import re
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from typing import Any, Literal, cast
from uuid import uuid4

from pathlib import Path

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from sqlalchemy.ext.asyncio import AsyncSession

from .auth import require_trading_admin, require_trading_admin_recent, require_user
from .database import SessionFactory, get_session
from .integrations.alpha_vantage import AlphaVantageClient, AlphaVantageError
from .integrations.ccxt_market import CcxtMarketClient, compact_pair, to_ccxt_symbol
from .integrations.kraken_cli import KrakenCli, KrakenCliError
from .integrations.kraken_public import KrakenPublicClient, normalize_orderbook_levels
from .integrations.paper_factory import build_paper_router
from .integrations.paper_router import PaperExecutionRouter
from .market.stream import get_market_stream_hub
from .paper_orders import PaperOrderService
from .schemas import (
    ClosePositionRequest,
    MarketBatchItem,
    MarketBatchResponse,
    OhlcvBatchResponse,
    OhlcvItem,
    OrderBookLevel,
    OrderBookResponse,
    PaperOrderRequest,
    PaperOrderResponse,
    TickerResponse,
)
from .settings import get_settings
from .routers.academy import router as academy_router
from .routers.ai import router as ai_router
from .routers.chronos import router as chronos_router
from .routers.market_stream import router as market_stream_router
from .routers.onnx import router as onnx_router
from .routers.telegram import router as telegram_router
from .routers.tvapi import router as tvapi_router
from .routers.vector import router as vector_router
from .routers.ga import router as ga_router
from .routers.loops import router as loops_router
from .routers.kraken_status import router as kraken_status_router
from .routers.orders import router as orders_router
from .routers.integrations_settings import router as integrations_settings_router
from .routers.tvremix import router as tvremix_router
from .integrations.onnx.paths import ensure_onnx_data_dir
from .integrations.onnx.runtime import ensure_seed_models, netron_static_dir, onnx_deps_available
from .academy.training_loop import training_loop
from .signals.mcp_server import mcp_router
from .signals.router import router as signal_router
from .signals.safety import assert_signals_module_imports
from .trading.autonomy import AutonomyLevel
from .trading.loops import trading_loops

logger = logging.getLogger("neo_fabel.api")
from .trading.session import Level4Session


def _kraken_status_snapshot() -> dict[str, Any]:
    try:
        from .integrations.kraken_status import load_index

        idx = load_index()
        if not idx:
            return {"loaded": False}
        non_op = idx.get("non_operational") or []
        return {
            "loaded": True,
            "fetched_at": idx.get("fetched_at"),
            "indicator": idx.get("indicator"),
            "description": idx.get("description"),
            "non_operational_count": len(non_op),
            "non_operational": [
                {"name": c.get("name"), "status": c.get("status")}
                for c in non_op
                if isinstance(c, dict)
            ][:20],
        }
    except Exception:  # noqa: BLE001 — health must not fail on status IO
        return {"loaded": False}


settings = get_settings()
COMMON_SYMBOLS = {
    "crypto": ["BTCUSD", "ETHUSD", "SOLUSD", "XRPUSD", "ADAUSD", "DOGEUSD", "AVAXUSD", "LINKUSD", "DOTUSD", "LTCUSD", "BCHUSD"],
    "forex": ["EURUSD", "GBPUSD", "USDJPY", "USDCHF", "AUDUSD", "USDCAD", "NZDUSD", "EURGBP", "EURJPY", "GBPJPY"],
    "sp500": ["SPY", "VOO", "IVV", "AAPL", "MSFT", "NVDA", "AMZN", "GOOGL", "META", "BRK.B", "TSLA", "AVGO", "JPM", "LLY", "XOM", "UNH", "COST", "WMT", "NFLX", "ORCL", "MA", "HD", "PG", "JNJ", "ABBV", "BAC", "CVX", "KO", "PEP", "AMD", "CRM", "CSCO", "IBM", "CAT", "GE"],
}
SYMBOL_RE = re.compile(r"^[A-Z0-9]+(?:[.-][A-Z0-9]+)?$")
INTRADAY_INTERVALS = {"1min", "5min", "15min", "30min", "60min", "4h"}


@asynccontextmanager
async def lifespan(_app: FastAPI):
    from .signals.engine.generator import FableEngine, set_fable_engine

    hub = get_market_stream_hub()
    await hub.start()
    if settings.opencode_config_write:
        from .integrations.opencode_config import write_opencode_config

        try:
            write_opencode_config(settings)
        except Exception:  # noqa: BLE001 — optional local tooling must not block API start
            logger.exception("opencode config write failed")
    if settings.signal_routes_enabled and settings.fable_engine_enabled:
        from .database import SessionFactory
        from .signals.bootstrap import ensure_fable_routes

        try:
            await ensure_fable_routes(SessionFactory, settings)
        except Exception:  # noqa: BLE001 — bootstrap must not block API start
            logger.exception("fable route bootstrap failed")
    if settings.training_loop_auto_start and settings.training_loop_enabled:
        await training_loop.start()
    engine_task: asyncio.Task | None = None
    if settings.fable_engine_enabled:
        from .database import SessionFactory

        engine = FableEngine(settings=settings, session_factory=SessionFactory)
        set_fable_engine(engine)
        engine_task = asyncio.create_task(engine.run_forever(), name="fable-engine")
    if settings.telegram_daemon_enabled:
        from .integrations.telegram_daemon import start_telegram_daemon

        try:
            await start_telegram_daemon(settings)
        except Exception:  # noqa: BLE001 — optional feed must not block API start
            logger.exception("telegram daemon start failed")
    try:
        yield
    finally:
        if settings.telegram_daemon_enabled:
            from .integrations.telegram_daemon import stop_telegram_daemon

            try:
                await stop_telegram_daemon()
            except Exception:  # noqa: BLE001
                logger.exception("telegram daemon stop failed")
        if engine_task is not None:
            from .signals.engine.generator import get_fable_engine

            running = get_fable_engine()
            if running is not None:
                running.stop()
            engine_task.cancel()
            try:
                await engine_task
            except asyncio.CancelledError:
                pass
            set_fable_engine(None)
        training_loop.stop_now()
        try:
            await trading_loops.shutdown()
        except Exception:  # noqa: BLE001
            logger.exception("trading loops shutdown failed")
        await hub.stop()


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


app = FastAPI(title="Neo Fabel API", version="1.0.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PATCH", "DELETE"],
    allow_headers=["Authorization", "Content-Type", "Idempotency-Key", "X-Request-ID"],
)
app.include_router(signal_router)
app.include_router(mcp_router)
app.include_router(ai_router)
app.include_router(tvapi_router)
app.include_router(telegram_router)
app.include_router(vector_router)
app.include_router(market_stream_router)
app.include_router(academy_router)
app.include_router(onnx_router)
app.include_router(chronos_router)
app.include_router(ga_router)
app.include_router(loops_router)
app.include_router(kraken_status_router)
app.include_router(orders_router)
app.include_router(integrations_settings_router)
app.include_router(tvremix_router)

# ONNX artifacts for Netron iframe (no Bearer — same-origin static only).
_onnx_dir = ensure_onnx_data_dir()
if onnx_deps_available():
    try:
        ensure_seed_models()
    except Exception:  # noqa: BLE001 — seed best-effort at import
        pass
app.mount("/static/onnx", StaticFiles(directory=str(_onnx_dir)), name="onnx_models")
_netron_dir = netron_static_dir()
if _netron_dir is None:
    _netron_dir = Path(__file__).resolve().parents[1] / "static" / "netron"
    _netron_dir.mkdir(parents=True, exist_ok=True)
app.mount("/static/netron", StaticFiles(directory=str(_netron_dir), html=True), name="netron")

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


def paper_router() -> PaperExecutionRouter:
    return build_paper_router(settings)


def _ledger_mark_targets(state: dict) -> tuple[list[str], list[str]]:
    """Return (spot_pairs, futures_pairs) needing mark prices from ledger state."""
    if int(state.get("version", 1)) >= 2:
        spot = state.get("spot") or {}
        futures = state.get("futures") or {}
        return list((spot.get("lots") or {}).keys()), list((futures.get("positions") or {}).keys())
    return list((state.get("lots") or {}).keys()), []


async def _collect_ledger_mark_prices(state: dict) -> dict:
    from decimal import Decimal, InvalidOperation

    from backend.app.integrations.kraken_futures_public import KrakenFuturesPublicClient

    spot_pairs, fut_pairs = _ledger_mark_targets(state)
    marks: dict[str, Decimal] = {}
    for pair in spot_pairs:
        try:
            ticker, _ = await crypto_ticker_data(pair)
            last = ticker.get("last") or ticker.get("price") or ticker.get("close")
            if isinstance(last, list) and last:
                last = last[0]
            if last is None or str(last).strip() in {"", "None", "null"}:
                continue
            marks[pair] = Decimal(str(last))
        except (KrakenCliError, InvalidOperation, ValueError, TypeError):
            continue
    if fut_pairs:
        futures_client = KrakenFuturesPublicClient(timeout_seconds=settings.kraken_timeout_seconds)
        for pair in fut_pairs:
            try:
                marks[pair] = await futures_client.last_price(pair)
            except KrakenCliError:
                try:
                    ticker, _ = await crypto_ticker_data(pair.replace("PF_", "").replace("XBT", "BTC"))
                    last = ticker.get("last") or ticker.get("price")
                    if isinstance(last, list) and last:
                        last = last[0]
                    if last is None or str(last).strip() in {"", "None", "null"}:
                        continue
                    marks[pair] = Decimal(str(last))
                except (KrakenCliError, InvalidOperation, ValueError, TypeError):
                    continue
    return marks


def level4_session() -> Level4Session:
    return Level4Session(settings, cli=kraken())


def alpha_vantage() -> AlphaVantageClient:
    return AlphaVantageClient(
        api_key=settings.alphavantage_api_key,
        base_url=settings.alphavantage_base_url,
        timeout_seconds=settings.alphavantage_timeout_seconds,
    )


def kraken_public() -> KrakenPublicClient:
    return KrakenPublicClient(timeout_seconds=settings.kraken_timeout_seconds)


def _normalize_cli_ticker(payload: dict[str, Any]) -> dict[str, Any]:
    """Normalize CLI ticker payloads into a flat dict with last/price/close."""
    entry: dict[str, Any] = payload
    if "last" not in payload and "price" not in payload and "close" not in payload:
        nested = next((value for value in payload.values() if isinstance(value, dict)), None)
        if isinstance(nested, dict):
            entry = dict(nested)
    close = entry.get("c")
    last = entry.get("last") or entry.get("price") or entry.get("close")
    if last is None and isinstance(close, list) and close:
        last = close[0]
    elif last is None:
        last = close
    if isinstance(last, list) and last:
        last = last[0]
    if last is not None:
        entry["last"] = last
        entry["price"] = last
        entry["close"] = last
    if "open" not in entry and entry.get("o") is not None:
        entry["open"] = entry.get("o")
    return entry


async def crypto_ticker_data(symbol: str) -> tuple[dict[str, Any], str]:
    """Prefer CLI; fall back to Kraken public REST (required on Windows uvicorn)."""
    try:
        raw = await kraken().ticker(symbol)
        return _normalize_cli_ticker(raw if isinstance(raw, dict) else {}), "kraken-cli"
    except KrakenCliError:
        data = await kraken_public().ticker(symbol)
        return data, "kraken-public"


def _normalize_cli_orderbook(pair: str, payload: dict[str, Any]) -> dict[str, Any]:
    """Normalize CLI orderbook payloads into {pair,bids,asks}."""
    book = payload
    if isinstance(payload.get("result"), dict):
        book = next((value for value in payload["result"].values() if isinstance(value, dict)), payload)
    bids_raw = book.get("bids") or book.get("Bids") or []
    asks_raw = book.get("asks") or book.get("Asks") or []
    return {
        "pair": pair.strip().upper().replace("/", "").replace("-", ""),
        "bids": normalize_orderbook_levels(bids_raw, reverse=True),
        "asks": normalize_orderbook_levels(asks_raw, reverse=False),
    }


async def crypto_orderbook_data(symbol: str, *, count: int = 25) -> tuple[dict[str, Any], str]:
    """Prefer CLI; fall back to Kraken public Depth (Windows-safe)."""
    try:
        raw = await kraken().orderbook(symbol, count=count)
        return _normalize_cli_orderbook(symbol, raw if isinstance(raw, dict) else {}), "kraken-cli"
    except KrakenCliError:
        data = await kraken_public().orderbook(symbol, count=count)
        return data, "kraken-public"


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
            "max_notional": str(guardrails.max_notional),
            "max_open_positions": guardrails.max_open_positions,
            "max_trades_per_hour": guardrails.max_trades_per_hour,
            "min_trade_interval_seconds": guardrails.min_trade_interval_seconds,
            "pair_allowlist": sorted(guardrails.pair_allowlist),
        },
        "live_algo_enabled": settings.kraken_live_algo_enabled,
        "required_for_level4": [
            "KRAKEN_AUTONOMY_LEVEL=4",
            "KRAKEN_LIVE_TRADING_ENABLED=true",
            "trade-only API key (no Withdraw Funds)",
            "dead man's switch armed each session",
            "KRAKEN_LIVE_ALGO_ENABLED=true only for unattended algo (manual desk OK without it)",
        ],
        "capital_policy": {
            "external_replenish": False,
            "negative_cash": False,
            "debt_or_leverage": False,
            "max_notional": str(settings.kraken_max_notional),
            "note": "System may only trade existing Kraken balances; deposit/withdraw/transfer blocked; no shorts or leverage>1",
        },
        "kraken_status": _kraken_status_snapshot(),
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
        result, _source = await crypto_ticker_data(pair)
    except KrakenCliError as exc:
        raise HTTPException(status_code=503, detail={"code": exc.category, "message": str(exc), "request_id": rid}) from exc
    return TickerResponse(pair=pair.upper(), data=result, as_of=datetime.now(UTC).isoformat(), request_id=rid)


@app.get("/api/v1/market/orderbook/{pair}", response_model=OrderBookResponse)
async def orderbook(pair: str, request: Request, count: int = 25) -> OrderBookResponse:
    rid = request_id(request)
    depth = max(1, min(count, 100))
    try:
        result, source = await crypto_orderbook_data(pair, count=depth)
    except KrakenCliError as exc:
        raise HTTPException(status_code=503, detail={"code": exc.category, "message": str(exc), "request_id": rid}) from exc
    return OrderBookResponse(
        pair=str(result.get("pair") or pair).upper(),
        bids=[OrderBookLevel(**level) for level in result.get("bids") or []],
        asks=[OrderBookLevel(**level) for level in result.get("asks") or []],
        source=source,
        as_of=datetime.now(UTC).isoformat(),
        request_id=rid,
    )


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

    crypto_symbols = symbol_groups.get("crypto", [])
    if crypto_symbols:
        used_ccxt = False
        if settings.market_ccxt_enabled:
            client: CcxtMarketClient | None = None
            try:
                client = CcxtMarketClient(
                    exchange_id=settings.market_ccxt_exchange,
                    timeout_ms=int(settings.kraken_timeout_seconds * 1000),
                )
                rows = await client.ticker_rows(crypto_symbols)
                by_pair = {str(row["pair"]): row for row in rows}
                for symbol in crypto_symbols:
                    pair = compact_pair(to_ccxt_symbol(symbol))
                    row = by_pair.get(pair) or by_pair.get(symbol.upper().replace("/", ""))
                    if row is None:
                        continue
                    items.append(
                        MarketBatchItem(
                            symbol=symbol,
                            asset_class="crypto",
                            status="ok",
                            source=f"ccxt:{settings.market_ccxt_exchange}",
                            data=row.get("data") or {
                                "last": row["price"],
                                "price": row["price"],
                                "change_pct": row.get("change"),
                                "symbol": row.get("symbol"),
                            },
                        )
                    )
                    used_ccxt = True
            except Exception:  # noqa: BLE001 — fall back to public REST
                used_ccxt = False
            finally:
                if client is not None:
                    await client.close()

        if not used_ccxt:
            # Public REST is the reliable fallback (Windows uvicorn cannot spawn kraken CLI).
            for symbol, payload in await kraken_public().ticker_for_symbols(crypto_symbols):
                if isinstance(payload, dict):
                    items.append(
                        MarketBatchItem(
                            symbol=symbol, asset_class="crypto", status="ok", source="kraken-public", data=payload
                        )
                    )
                else:
                    err = payload if isinstance(payload, KrakenCliError) else KrakenCliError("api", str(payload))
                    items.append(
                        MarketBatchItem(
                            symbol=symbol,
                            asset_class="crypto",
                            status="error",
                            source="kraken-public",
                            error={"code": err.category, "message": str(err)},
                        )
                    )

    av = alpha_vantage()
    for symbol, result in await av.forex_batch(symbol_groups.get("forex", []), settings.alphavantage_batch_concurrency):
        if isinstance(result, Exception):
            category = result.category if isinstance(result, AlphaVantageError) else "provider"
            items.append(MarketBatchItem(symbol=symbol, asset_class="forex", status="error", source="alpha-vantage", error={"code": category, "message": str(result)}))
        else:
            items.append(MarketBatchItem(symbol=symbol, asset_class="forex", status="ok", source="alpha-vantage", data=result))

    equities = symbol_groups.get("sp500", [])
    if equities:
        # Prefer per-symbol GLOBAL_QUOTE (works on free keys). Optional bulk when explicitly enabled.
        if settings.alphavantage_bulk_quotes_enabled and len(equities) > 1:
            try:
                result = await av.equity_bulk(equities)
                for symbol in equities:
                    items.append(
                        MarketBatchItem(
                            symbol=symbol, asset_class="sp500", status="ok", source="alpha-vantage-bulk", data=result
                        )
                    )
            except AlphaVantageError:
                for symbol, result in await av.equity_quotes_batch(
                    equities, concurrency=settings.alphavantage_batch_concurrency
                ):
                    if isinstance(result, Exception):
                        category = result.category if isinstance(result, AlphaVantageError) else "provider"
                        items.append(
                            MarketBatchItem(
                                symbol=symbol,
                                asset_class="sp500",
                                status="error",
                                source="alpha-vantage",
                                error={"code": category, "message": str(result)},
                            )
                        )
                    else:
                        items.append(
                            MarketBatchItem(
                                symbol=symbol, asset_class="sp500", status="ok", source="alpha-vantage", data=result
                            )
                        )
        else:
            for symbol, result in await av.equity_quotes_batch(
                equities, concurrency=settings.alphavantage_batch_concurrency
            ):
                if isinstance(result, Exception):
                    category = result.category if isinstance(result, AlphaVantageError) else "provider"
                    items.append(
                        MarketBatchItem(
                            symbol=symbol,
                            asset_class="sp500",
                            status="error",
                            source="alpha-vantage",
                            error={"code": category, "message": str(result)},
                        )
                    )
                else:
                    items.append(
                        MarketBatchItem(
                            symbol=symbol, asset_class="sp500", status="ok", source="alpha-vantage", data=result
                        )
                    )

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
        data = await paper_router().paper_status()
        return {"mode": "paper", "data": data, "request_id": rid, "execution": "paper-only"}
    except KrakenCliError as exc:
        raise HTTPException(status_code=503, detail={"code": exc.category, "message": str(exc), "request_id": rid}) from exc


@app.get("/api/v1/paper/performance")
async def paper_performance(request: Request, _user: dict = Depends(require_user)) -> dict:
    """Paper-only performance snapshot: equity, FIFO PnL, positions, fills."""
    from decimal import Decimal

    rid = request_id(request)
    router = paper_router()
    try:
        mark_prices = await _collect_ledger_mark_prices(router.ledger.snapshot_state())
        perf = await router.paper_performance(mark_prices)
        return {
            "mode": "paper",
            "execution": "paper-only",
            "request_id": rid,
            "router_source": router.last_source,
            **perf,
        }
    except KrakenCliError as exc:
        raise HTTPException(status_code=503, detail={"code": exc.category, "message": str(exc), "request_id": rid}) from exc


@app.get("/api/v1/positions")
async def list_positions(request: Request, _user: dict = Depends(require_user)) -> dict:
    """Open positions: paper ledger lots + Kraken live balances (read-only when live disabled)."""
    from decimal import Decimal

    from backend.app.integrations.positions import build_positions_snapshot

    rid = request_id(request)
    router = paper_router()
    mark_prices = await _collect_ledger_mark_prices(router.ledger.snapshot_state())
    perf = await router.paper_performance(mark_prices)
    snapshot = await build_positions_snapshot(
        paper_positions=perf.get("positions") or [],
        cli=kraken(),
        ticker_fn=crypto_ticker_data,
        live_trading_enabled=settings.kraken_live_trading_enabled,
        trade_commands_enabled=settings.trade_commands_enabled,
    )
    return {
        "request_id": rid,
        "execution": "live-autonomous" if settings.trade_commands_enabled else "paper-only",
        "autonomy_level": int(settings.autonomy),
        **snapshot,
    }


@app.post("/api/v1/positions/close")
async def close_position(
    payload: ClosePositionRequest,
    request: Request,
    user: dict = Depends(require_user),
) -> PaperOrderResponse:
    """Close (flatten) a paper or live position via market/limit sell."""
    from decimal import Decimal

    rid = request_id(request)
    pair = payload.pair.strip().upper().replace("/", "").replace("-", "")

    if payload.mode == "paper":
        router = paper_router()
        open_vol = router.ledger.open_volume(pair, market_type=payload.market_type)
        if open_vol <= 0:
            raise HTTPException(
                status_code=404,
                detail={"code": "no_position", "message": f"no paper position for {pair}", "request_id": rid},
            )
        volume = payload.volume or open_vol
        if volume > open_vol:
            raise HTTPException(
                status_code=422,
                detail={"code": "volume_exceeds_position", "message": str(open_vol), "request_id": rid},
            )
        order_req = PaperOrderRequest(
            pair=pair,
            side="sell",
            volume=volume,
            order_type=payload.order_type,
            price=payload.price,
            market_type=payload.market_type,
            idempotency_key=payload.idempotency_key,
        )
        return await _place_paper_order(order_req, user, rid)

    # Live close — supervised manual exit (Level 3+) with live flag + trade commands
    if not settings.kraken_live_trading_enabled or not settings.trade_commands_enabled:
        raise HTTPException(
            status_code=403,
            detail={
                "code": "live_trading_disabled",
                "message": "Live position close requires KRAKEN_LIVE_TRADING_ENABLED and autonomy >= 3",
                "request_id": rid,
            },
        )
    if settings.autonomy < AutonomyLevel.SUPERVISED:
        raise HTTPException(
            status_code=403,
            detail={"code": "autonomy_too_low", "message": "supervised autonomy (3+) required", "request_id": rid},
        )

    balance = await kraken().balance()
    from backend.app.integrations.positions import parse_live_balances

    live_rows = parse_live_balances(balance if isinstance(balance, dict) else None)
    row = next((r for r in live_rows if r["pair"] == pair), None)
    if row is None:
        raise HTTPException(
            status_code=404,
            detail={"code": "no_position", "message": f"no live balance for {pair}", "request_id": rid},
        )
    volume = payload.volume or Decimal(str(row["volume"]))
    guardrails = settings.trading_guardrails()
    try:
        normalized = guardrails.check_order(pair=pair, volume=volume, open_positions=0)
        await kraken().validate_order("sell", normalized, volume, payload.order_type, payload.price)
        result = await kraken().place_order(
            "sell", normalized, volume, payload.order_type, payload.price, yes=True
        )
    except KrakenCliError as exc:
        status = 503 if exc.retryable else 422
        raise HTTPException(
            status_code=status,
            detail={"code": exc.category, "message": str(exc), "request_id": rid},
        ) from exc
    return PaperOrderResponse(
        idempotency_key=payload.idempotency_key,
        status="ACCEPTED",
        result=result if isinstance(result, dict) else {"raw": result},
        request_id=rid,
    )


@app.get("/api/v1/trade/positions")
async def trade_positions(request: Request, user: dict = Depends(require_user)) -> dict:
    """Unified positions snapshot (paper + live)."""
    return await list_positions(request, user)


async def _place_paper_order(payload: PaperOrderRequest, user: dict, rid: str) -> PaperOrderResponse:
    """Persist via Postgres when up; otherwise accept into the local paper ledger."""
    router = paper_router()
    try:
        async with SessionFactory() as session:
            service = PaperOrderService(sink=router)
            return await service.place_manual(
                session=session,
                user_uid=str(user.get("uid", "")),
                payload=payload,
                request_id=rid,
            )
    except HTTPException as exc:
        detail = exc.detail if isinstance(exc.detail, dict) else {}
        if exc.status_code != 503 or detail.get("code") != "database_unavailable":
            raise
    except Exception:
        # Connection refused / asyncpg / engine errors when Postgres is down.
        pass

    try:
        result = await router.paper_order(
            payload.side,
            payload.pair,
            payload.volume,
            payload.order_type,
            payload.price,
            market_type=payload.market_type,
            leverage=payload.leverage,
        )
    except (KrakenCliError, ValueError) as sink_exc:
        raise HTTPException(
            status_code=503,
            detail={"code": "paper_unavailable", "message": str(sink_exc), "request_id": rid},
        ) from sink_exc
    return PaperOrderResponse(
        idempotency_key=payload.idempotency_key,
        status="ACCEPTED",
        result=result if isinstance(result, dict) else {"raw": result},
        request_id=rid,
    )


@app.post("/api/v1/paper/orders", response_model=PaperOrderResponse)
async def paper_order(
    payload: PaperOrderRequest,
    request: Request,
    user: dict = Depends(require_user),
) -> PaperOrderResponse:
    return await _place_paper_order(payload, user, request_id(request))


@app.post("/api/v1/trade/execute", response_model=PaperOrderResponse)
async def trade_execute(
    payload: PaperOrderRequest,
    request: Request,
    user: dict = Depends(require_user),
) -> PaperOrderResponse:
    """Phase 3 alias — always paper-routed (live trading stays gated elsewhere)."""
    return await _place_paper_order(payload, user, request_id(request))
