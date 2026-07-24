"""Candle sourcing for FableEngine — tvremix get_ohlcv primary, CCXT fallback.

Verified tvremix shape (live, 2026-07-20): {"bars": [{t, o, h, l, c, v}, ...]},
timestamps in Unix seconds (UTC). CCXT rows are [ts_ms, o, h, l, c, v].
Both normalize to: {timestamp (s), open, high, low, close, volume}.
Never Alpha Vantage here (daily free-tier cap is unfit for a poll loop).
"""

from __future__ import annotations

import logging
from typing import Any

from backend.app.settings import Settings

logger = logging.getLogger("neo_fabel.signals.engine.market")

# tvremix-supported intervals; ccxt uses lowercase day/week but capital M for month.
_CCXT_INTERVALS: dict[str, str] = {
    "1m": "1m",
    "5m": "5m",
    "15m": "15m",
    "30m": "30m",
    "1h": "1h",
    "4h": "4h",
    "1D": "1d",
    "1W": "1w",
    "1M": "1M",
}
_DEFAULT_INTERVAL = "5m"


def resolve_source(settings: Settings) -> str:
    """Pick candle source: explicit setting wins; auto prefers tvremix when keyed."""
    configured = (settings.fable_engine_candle_source or "auto").strip().lower()
    if configured == "tvremix":
        return "tvremix"
    if configured == "ccxt":
        return "ccxt"
    has_key = bool((settings.tvremix_api_key or "").strip())
    if settings.tvremix_enabled and has_key:
        return "tvremix"
    return "ccxt"


def normalize_interval(interval: str, *, for_ccxt: bool = False) -> str:
    value = (interval or _DEFAULT_INTERVAL).strip()
    if value not in _CCXT_INTERVALS:
        value = _DEFAULT_INTERVAL
    if for_ccxt:
        return _CCXT_INTERVALS[value]
    return value


def bars_to_candles(raw: Any) -> list[dict[str, Any]]:
    """Pure mapper for the tvremix get_ohlcv payload (t/o/h/l/c/v keys)."""
    bars: list[Any] = []
    if isinstance(raw, dict):
        maybe = raw.get("bars")
        if isinstance(maybe, list):
            bars = maybe
    elif isinstance(raw, list):
        bars = raw
    candles: list[dict[str, Any]] = []
    for bar in bars:
        if not isinstance(bar, dict):
            continue
        close = bar.get("c", bar.get("close"))
        if close is None:
            continue
        ts_raw = bar.get("t", bar.get("timestamp"))
        try:
            timestamp = int(ts_raw) if ts_raw is not None else 0
        except (TypeError, ValueError):
            timestamp = 0
        open_value = bar.get("o", bar.get("open"))
        high_value = bar.get("h", bar.get("high"))
        low_value = bar.get("l", bar.get("low"))
        candles.append(
            {
                "timestamp": timestamp,
                "open": float(close if open_value is None else open_value),
                "high": float(close if high_value is None else high_value),
                "low": float(close if low_value is None else low_value),
                "close": float(close),
                "volume": float(bar.get("v", bar.get("volume", 0.0)) or 0.0),
            }
        )
    return candles


def ccxt_rows_to_candles(rows: Any) -> list[dict[str, Any]]:
    """Pure mapper for CCXT OHLCV rows ([ts_ms, o, h, l, c, v])."""
    candles: list[dict[str, Any]] = []
    for row in rows or []:
        if not isinstance(row, (list, tuple)) or len(row) < 5:
            continue
        try:
            candles.append(
                {
                    "timestamp": int(row[0]) // 1000,
                    "open": float(row[1]),
                    "high": float(row[2]),
                    "low": float(row[3]),
                    "close": float(row[4]),
                    "volume": float(row[5]) if len(row) > 5 else 0.0,
                }
            )
        except (TypeError, ValueError):
            continue
    return candles


async def fetch_candles(pair: str, *, settings: Settings, count: int = 120) -> list[dict[str, Any]]:
    """Fetch candles for one pair; tvremix errors fall back to ccxt, never raise."""
    source = resolve_source(settings)
    if source == "tvremix":
        try:
            return await _fetch_tvremix(pair, settings=settings, count=count)
        except Exception as exc:  # noqa: BLE001 — engine tick must survive provider failure
            logger.warning("tvremix candles failed for %s (%s); falling back to ccxt", pair, exc)
    try:
        return await _fetch_ccxt(pair, settings=settings, count=count)
    except Exception as exc:  # noqa: BLE001
        logger.warning("ccxt candles failed for %s (%s); returning empty", pair, exc)
        return []


async def _fetch_tvremix(pair: str, *, settings: Settings, count: int) -> list[dict[str, Any]]:
    from backend.app.integrations.tvremix_client import TvremixClient, _to_tv_symbol

    interval = normalize_interval(settings.fable_engine_interval)
    client = TvremixClient(settings)
    raw = await client.call_tool(
        "get_ohlcv",
        {
            "symbol": _to_tv_symbol(pair),
            "interval": interval,
            "count": min(max(count, 10), 5000),
            "summary": False,
        },
    )
    return bars_to_candles(raw)


async def _fetch_ccxt(pair: str, *, settings: Settings, count: int) -> list[dict[str, Any]]:
    from backend.app.integrations.ccxt_market import CcxtMarketClient

    interval = normalize_interval(settings.fable_engine_interval, for_ccxt=True)
    client = CcxtMarketClient(exchange_id=settings.market_ccxt_exchange)
    try:
        rows = await client.fetch_ohlcv(pair, timeframe=interval, limit=min(max(count, 10), 720))
        return ccxt_rows_to_candles(rows)
    finally:
        await client.close()
