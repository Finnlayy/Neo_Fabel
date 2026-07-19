"""In-process market ticker broadcaster for FastAPI WebSocket clients.

Polls CCXT (or Kraken public REST fallback) on an interval and fans out
normalized ticker snapshots. Read-only — never touches order APIs.
"""

from __future__ import annotations

import asyncio
import logging
from collections import defaultdict, deque
from datetime import UTC, datetime
from typing import Any

from fastapi import WebSocket
from starlette.websockets import WebSocketDisconnect, WebSocketState

from ..integrations.ccxt_market import DEFAULT_CCXT_SYMBOLS, CcxtMarketClient, display_base, to_ccxt_symbol
from ..integrations.kraken_cli import KrakenCliError
from ..integrations.kraken_public import KrakenPublicClient
from ..settings import Settings, get_settings

logger = logging.getLogger(__name__)

HISTORY_LEN = 24


class MarketStreamHub:
    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()
        self._clients: set[WebSocket] = set()
        self._lock = asyncio.Lock()
        self._task: asyncio.Task[None] | None = None
        self._ccxt: CcxtMarketClient | None = None
        self._latest: dict[str, Any] | None = None
        self._history: dict[str, deque[float]] = defaultdict(lambda: deque(maxlen=HISTORY_LEN))
        self._source = "idle"
        self._last_error: str | None = None

    @property
    def enabled(self) -> bool:
        return self.settings.market_stream_enabled

    @property
    def client_count(self) -> int:
        return len(self._clients)

    def health(self) -> dict[str, Any]:
        return {
            "enabled": self.enabled,
            "running": self._task is not None and not self._task.done(),
            "clients": self.client_count,
            "source": self._source,
            "ccxt_enabled": self.settings.market_ccxt_enabled,
            "exchange": self.settings.market_ccxt_exchange,
            "interval_seconds": self.settings.market_stream_interval_seconds,
            "last_error": self._last_error,
            "as_of": None if self._latest is None else self._latest.get("as_of"),
            "ticker_count": 0 if self._latest is None else len(self._latest.get("tickers") or []),
        }

    async def start(self) -> None:
        if not self.enabled:
            logger.info("market stream disabled (MARKET_STREAM_ENABLED=false)")
            return
        if self._task is not None and not self._task.done():
            return
        if self.settings.market_ccxt_enabled:
            self._ccxt = CcxtMarketClient(
                exchange_id=self.settings.market_ccxt_exchange,
                timeout_ms=int(self.settings.kraken_timeout_seconds * 1000),
            )
        self._task = asyncio.create_task(self._loop(), name="market-stream-hub")
        logger.info(
            "market stream started exchange=%s interval=%s",
            self.settings.market_ccxt_exchange,
            self.settings.market_stream_interval_seconds,
        )

    async def stop(self) -> None:
        task = self._task
        self._task = None
        if task is not None:
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
        if self._ccxt is not None:
            await self._ccxt.close()
            self._ccxt = None
        async with self._lock:
            clients = list(self._clients)
            self._clients.clear()
        for client in clients:
            try:
                await client.close()
            except Exception:  # noqa: BLE001
                pass

    async def register(self, websocket: WebSocket) -> None:
        await websocket.accept()
        async with self._lock:
            self._clients.add(websocket)
        hello = {
            "type": "hello",
            "source": self._source,
            "exchange": self.settings.market_ccxt_exchange,
            "as_of": datetime.now(UTC).isoformat(),
        }
        await websocket.send_json(hello)
        if self._latest is not None:
            await websocket.send_json(self._latest)

    async def unregister(self, websocket: WebSocket) -> None:
        async with self._lock:
            self._clients.discard(websocket)

    async def serve(self, websocket: WebSocket) -> None:
        await self.register(websocket)
        try:
            while True:
                # Keep the socket alive; clients may send pings/empty frames.
                message = await websocket.receive_text()
                if message.strip().lower() in {"ping", '{"type":"ping"}'}:
                    await websocket.send_json({"type": "pong", "as_of": datetime.now(UTC).isoformat()})
        except WebSocketDisconnect:
            pass
        finally:
            await self.unregister(websocket)

    async def _loop(self) -> None:
        interval = max(1.0, float(self.settings.market_stream_interval_seconds))
        while True:
            try:
                snapshot = await self._fetch_snapshot()
                self._latest = snapshot
                self._last_error = None
                await self._broadcast(snapshot)
            except asyncio.CancelledError:
                raise
            except Exception as exc:  # noqa: BLE001 — keep loop alive
                self._last_error = str(exc)
                self._source = "error"
                logger.warning("market stream fetch failed: %s", exc)
                await self._broadcast(
                    {
                        "type": "error",
                        "message": "market_stream_fetch_failed",
                        "as_of": datetime.now(UTC).isoformat(),
                    }
                )
            await asyncio.sleep(interval)

    def _symbols(self) -> list[str]:
        raw = self.settings.market_stream_symbols.strip()
        if not raw:
            return list(DEFAULT_CCXT_SYMBOLS)
        return [part.strip() for part in raw.split(",") if part.strip()]

    async def _fetch_snapshot(self) -> dict[str, Any]:
        symbols = self._symbols()
        rows: list[dict[str, Any]] = []
        source = "none"

        if self._ccxt is not None:
            try:
                rows = await self._ccxt.ticker_rows(symbols)
                source = f"ccxt:{self.settings.market_ccxt_exchange}"
            except Exception as exc:  # noqa: BLE001 — fall back
                logger.info("ccxt stream fetch failed, falling back to kraken-public: %s", exc)
                rows = []

        if not rows:
            rows = await self._fetch_via_kraken_public(symbols)
            source = "kraken-public"

        tickers: list[dict[str, Any]] = []
        for row in rows:
            symbol = str(row["symbol"])
            price = float(row["price"])
            hist = self._history[symbol]
            hist.append(price)
            tickers.append(
                {
                    "symbol": symbol,
                    "name": row["name"],
                    "price": price,
                    "change": float(row.get("change") or 0.0),
                    "history": list(hist),
                }
            )

        self._source = source
        return {
            "type": "tickers",
            "source": source,
            "as_of": datetime.now(UTC).isoformat(),
            "tickers": tickers,
        }

    async def _fetch_via_kraken_public(self, symbols: list[str]) -> list[dict[str, Any]]:
        compact = [to_ccxt_symbol(symbol).replace("/", "") for symbol in symbols]
        # Prefer original compact aliases for Kraken public (BTCUSD not BTC/USD).
        client = KrakenPublicClient(timeout_seconds=self.settings.kraken_timeout_seconds)
        rows: list[dict[str, Any]] = []
        for symbol, payload in await client.ticker_for_symbols(compact):
            if isinstance(payload, Exception):
                continue
            if not isinstance(payload, dict):
                continue
            last = payload.get("last") or payload.get("price") or payload.get("close")
            try:
                price = float(last)  # type: ignore[arg-type]
            except (TypeError, ValueError):
                continue
            if price <= 0:
                continue
            open_ = payload.get("open")
            change = 0.0
            try:
                open_f = float(open_) if open_ is not None else None  # type: ignore[arg-type]
                if open_f and open_f > 0:
                    change = ((price - open_f) / open_f) * 100.0
            except (TypeError, ValueError):
                change = 0.0
            base = display_base(to_ccxt_symbol(symbol))
            from ..integrations.ccxt_market import SYMBOL_NAMES

            rows.append(
                {
                    "symbol": base,
                    "name": SYMBOL_NAMES.get(base, base),
                    "price": price,
                    "change": change,
                    "pair": symbol,
                }
            )
        if not rows:
            raise KrakenCliError("api", "no public ticker rows for stream symbols")
        return rows

    async def _broadcast(self, message: dict[str, Any]) -> None:
        async with self._lock:
            clients = list(self._clients)
        stale: list[WebSocket] = []
        for client in clients:
            if client.client_state != WebSocketState.CONNECTED:
                stale.append(client)
                continue
            try:
                await client.send_json(message)
            except Exception:  # noqa: BLE001
                stale.append(client)
        if stale:
            async with self._lock:
                for client in stale:
                    self._clients.discard(client)


_hub: MarketStreamHub | None = None


def get_market_stream_hub() -> MarketStreamHub:
    global _hub
    if _hub is None:
        _hub = MarketStreamHub()
    return _hub


def reset_market_stream_hub_for_tests() -> None:
    global _hub
    _hub = None
