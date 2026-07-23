"""Read-only CCXT market data adapter (Phase 2).

Public ticker/OHLCV only — never constructs an authenticated exchange session
and never exposes order/trade methods.
"""

from __future__ import annotations

import asyncio
from typing import Any

import ccxt.async_support as ccxt

from .kraken_cli import KrakenCliError

# Display base → human name (matches frontend market.ts).
SYMBOL_NAMES: dict[str, str] = {
    "BTC": "Bitcoin",
    "ETH": "Ethereum",
    "SOL": "Solana",
    "MATIC": "Polygon",
    "POL": "Polygon",
    "AVAX": "Avalanche",
    "DOT": "Polkadot",
    "XRP": "Ripple",
    "ADA": "Cardano",
    "DOGE": "Dogecoin",
    "LINK": "Chainlink",
    "LTC": "Litecoin",
    "BCH": "Bitcoin Cash",
}

# Compact app pair (BTCUSD) → CCXT unified symbol.
COMPACT_TO_CCXT: dict[str, str] = {
    "BTCUSD": "BTC/USD",
    "ETHUSD": "ETH/USD",
    "SOLUSD": "SOL/USD",
    "XRPUSD": "XRP/USD",
    "ADAUSD": "ADA/USD",
    "DOGEUSD": "DOGE/USD",
    "AVAXUSD": "AVAX/USD",
    "LINKUSD": "LINK/USD",
    "DOTUSD": "DOT/USD",
    "LTCUSD": "LTC/USD",
    "BCHUSD": "BCH/USD",
    "MATICUSD": "POL/USD",
    "POLUSD": "POL/USD",
}

DEFAULT_CCXT_SYMBOLS = [
    "BTC/USD",
    "ETH/USD",
    "SOL/USD",
    "XRP/USD",
    "ADA/USD",
    "AVAX/USD",
    "DOT/USD",
    "POL/USD",
]


def compact_pair(ccxt_symbol: str) -> str:
    """BTC/USD → BTCUSD."""
    return ccxt_symbol.replace("/", "").replace("-", "").upper()


def to_ccxt_symbol(pair: str) -> str:
    normalized = pair.strip().upper().replace("-", "/")
    if "/" in normalized:
        return normalized
    compact = normalized.replace("/", "")
    return COMPACT_TO_CCXT.get(compact, f"{compact[:-3]}/{compact[-3:]}" if len(compact) > 3 else compact)


def display_base(ccxt_symbol: str) -> str:
    base = ccxt_symbol.split("/")[0].upper()
    return "MATIC" if base == "POL" else base


class CcxtMarketClient:
    """Thin public-market wrapper around a CCXT exchange (default: kraken)."""

    FORBIDDEN_METHODS = frozenset(
        {
            "create_order",
            "createOrder",
            "create_market_order",
            "create_limit_order",
            "cancel_order",
            "cancelOrder",
            "private_post",
            "withdraw",
        }
    )

    def __init__(
        self,
        *,
        exchange_id: str = "kraken",
        timeout_ms: int = 15000,
    ) -> None:
        if not hasattr(ccxt, exchange_id):
            raise ValueError(f"unsupported CCXT exchange: {exchange_id}")
        exchange_cls = getattr(ccxt, exchange_id)
        # Intentionally no apiKey/secret — public market endpoints only.
        self._exchange = exchange_cls(
            {
                "enableRateLimit": True,
                "timeout": timeout_ms,
            }
        )
        self.exchange_id = exchange_id
        self._assert_read_only_surface()

    def _assert_read_only_surface(self) -> None:
        """Fail closed if someone later wires credentials onto this client."""
        credentials = getattr(self._exchange, "apiKey", None) or getattr(self._exchange, "secret", None)
        if credentials:
            raise RuntimeError("CcxtMarketClient must not carry API credentials")

    async def close(self) -> None:
        try:
            await self._exchange.close()
        except Exception:  # noqa: BLE001 — best-effort shutdown
            pass

    async def fetch_tickers(self, symbols: list[str]) -> dict[str, dict[str, Any]]:
        """Return CCXT unified ticker dicts keyed by CCXT symbol."""
        unified = [to_ccxt_symbol(symbol) for symbol in symbols]
        try:
            if hasattr(self._exchange, "fetch_tickers"):
                raw = await self._exchange.fetch_tickers(unified)
            else:
                raw = {}
                tasks = [self._exchange.fetch_ticker(symbol) for symbol in unified]
                results = await asyncio.gather(*tasks)
                for symbol, result in zip(unified, results):
                    raw[symbol] = result
        except ccxt.BaseError as exc:
            raise KrakenCliError("api", f"ccxt ticker failed: {exc}", retryable=True) from exc
        if not isinstance(raw, dict):
            raise KrakenCliError("parse", "ccxt ticker returned unexpected payload")
        return {str(key): value for key, value in raw.items() if isinstance(value, dict)}

    async def fetch_ohlcv(
        self,
        symbol: str,
        *,
        timeframe: str = "1m",
        limit: int = 100,
    ) -> list[list[Any]]:
        try:
            return await self._exchange.fetch_ohlcv(to_ccxt_symbol(symbol), timeframe=timeframe, limit=limit)
        except ccxt.BaseError as exc:
            raise KrakenCliError("api", f"ccxt ohlcv failed: {exc}", retryable=True) from exc

    def normalize_ticker(self, ccxt_symbol: str, ticker: dict[str, Any]) -> dict[str, Any]:
        """Map a CCXT ticker into the app's last/open/change_pct shape."""
        last = _num(ticker.get("last")) or _num(ticker.get("close"))
        open_ = _num(ticker.get("open"))
        percentage = _num(ticker.get("percentage"))
        if percentage is None and last is not None and open_ is not None and open_ > 0:
            percentage = ((last - open_) / open_) * 100.0
        base = display_base(ccxt_symbol)
        return {
            "last": last,
            "price": last,
            "close": last,
            "open": open_,
            "change_pct": percentage if percentage is not None else 0.0,
            "symbol": base,
            "ccxt_symbol": ccxt_symbol,
            "bid": _num(ticker.get("bid")),
            "ask": _num(ticker.get("ask")),
            "high": _num(ticker.get("high")),
            "low": _num(ticker.get("low")),
            "baseVolume": _num(ticker.get("baseVolume")),
        }

    async def ticker_rows(self, symbols: list[str]) -> list[dict[str, Any]]:
        """Normalized rows for stream/UI: symbol, name, price, change."""
        tickers = await self.fetch_tickers(symbols)
        rows: list[dict[str, Any]] = []
        for symbol in symbols:
            ccxt_symbol = to_ccxt_symbol(symbol)
            payload = tickers.get(ccxt_symbol)
            if payload is None:
                # Some exchanges key by alternate id — scan values.
                for key, value in tickers.items():
                    if to_ccxt_symbol(key) == ccxt_symbol or key.replace("/", "") == compact_pair(ccxt_symbol):
                        payload = value
                        break
            if not isinstance(payload, dict):
                continue
            normalized = self.normalize_ticker(ccxt_symbol, payload)
            last = normalized.get("last")
            if last is None or float(last) <= 0:
                continue
            base = display_base(ccxt_symbol)
            rows.append(
                {
                    "symbol": base,
                    "name": SYMBOL_NAMES.get(base, base),
                    "price": float(last),
                    "change": float(normalized.get("change_pct") or 0.0),
                    "pair": compact_pair(ccxt_symbol),
                    "data": normalized,
                }
            )
        return rows


def _num(value: Any) -> float | None:
    if value is None:
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if number != number:  # NaN
        return None
    return number
