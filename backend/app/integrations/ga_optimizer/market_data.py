"""OHLCV fetch/cache for the GA optimizer (httpx / ccxt / disk cache — no requests)."""

from __future__ import annotations

import json
import logging
from collections.abc import Sequence
from pathlib import Path
from typing import Any

import httpx

from .engine import Candle, MarketPacks, build_symbol_pack

logger = logging.getLogger("neo_fabel.ga.market_data")

BINANCE_FAPI = "https://fapi.binance.com"
CISD_LENS = [3, 4, 5, 6, 7, 8]


def candles_from_rows(rows: Sequence[dict[str, Any] | list[Any]]) -> list[Candle]:
    out: list[Candle] = []
    for row in rows:
        if isinstance(row, dict):
            ts = int(row.get("timestamp") or row.get("ts") or row.get("t") or 0)
            o = float(row["open"] if "open" in row else row["o"])
            h = float(row["high"] if "high" in row else row["h"])
            low = float(row["low"] if "low" in row else row["l"])
            c = float(row["close"] if "close" in row else row["c"])
            v = float(row.get("volume") or row.get("v") or 0.0)
            out.append(Candle(ts, o, h, low, c, v))
        else:
            # Binance kline array shape
            out.append(
                Candle(
                    int(row[0]),
                    float(row[1]),
                    float(row[2]),
                    float(row[3]),
                    float(row[4]),
                    float(row[5]),
                )
            )
    return out


def load_cache_candles(cache_dir: Path, symbol: str, lookback_bars: int) -> list[Candle] | None:
    """Load {SYMBOL}_15m.json or {SYMBOL}_15m_*.json from cache_dir."""
    sym = symbol.upper().replace("/", "").replace("-", "")
    candidates = [
        cache_dir / f"{sym}_15m.json",
        cache_dir / f"{sym}_15m_4000.json",
        cache_dir / f"{sym}_15m_sample.json",
    ]
    # Also accept bare listings like ETHUSDT_15m_*.json via glob
    if not any(p.exists() for p in candidates):
        matches = sorted(cache_dir.glob(f"{sym}_15m*.json"))
        candidates = matches
    for path in candidates:
        if not path.exists():
            continue
        data = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(data, dict) and "candles" in data:
            data = data["candles"]
        if not isinstance(data, list) or not data:
            continue
        candles = candles_from_rows(data)
        if lookback_bars > 0 and len(candles) > lookback_bars:
            candles = candles[-lookback_bars:]
        return candles
    return None


def list_cache_symbols(cache_dir: Path) -> list[str]:
    if not cache_dir.exists():
        return []
    symbols: list[str] = []
    for path in sorted(cache_dir.glob("*_15m*.json")):
        name = path.name
        # ETHUSDT_15m.json / ETHUSDT_15m_4000.json
        base = name.split("_15m")[0].upper()
        if base and base not in symbols:
            symbols.append(base)
    return symbols


def fetch_klines_binance(
    symbol: str, interval: str, limit: int, *, timeout: float = 30.0
) -> list[Candle]:
    params: dict[str, str | int] = {
        "symbol": symbol.upper(),
        "interval": interval,
        "limit": min(limit, 1500),
    }
    with httpx.Client(timeout=timeout) as client:
        r = client.get(f"{BINANCE_FAPI}/fapi/v1/klines", params=params)
        r.raise_for_status()
        data = r.json()
    return candles_from_rows(data)


def exchange_symbols_binance(*, max_symbols: int, timeout: float = 30.0) -> list[tuple[str, float]]:
    with httpx.Client(timeout=timeout) as client:
        ex = client.get(f"{BINANCE_FAPI}/fapi/v1/exchangeInfo")
        ex.raise_for_status()
        tick = client.get(f"{BINANCE_FAPI}/fapi/v1/ticker/24hr")
        tick.raise_for_status()
        ex_data = ex.json()
        tick_data = tick.json()
    vol = {r["symbol"]: float(r.get("quoteVolume", 0.0)) for r in tick_data}
    out: list[tuple[str, float]] = []
    for s in ex_data["symbols"]:
        if (
            s.get("status") == "TRADING"
            and s.get("quoteAsset") == "USDT"
            and s.get("contractType") == "PERPETUAL"
        ):
            sym = s["symbol"]
            out.append((sym, vol.get(sym, 0.0)))
    out.sort(key=lambda x: x[1], reverse=True)
    if max_symbols > 0:
        out = out[:max_symbols]
    return out


def fetch_klines_ccxt(
    symbol: str, timeframe: str, limit: int, *, exchange_id: str = "binanceusdm"
) -> list[Candle]:
    """Optional ccxt path (sync). Symbol like ETHUSDT → ETH/USDT:USDT when needed."""
    import ccxt  # local import — optional path

    exchange_cls = getattr(ccxt, exchange_id, None)
    if exchange_cls is None:
        raise ValueError(f"Unknown ccxt exchange: {exchange_id}")
    ex = exchange_cls({"enableRateLimit": True})
    try:
        unified = symbol
        if "/" not in symbol:
            # ETHUSDT → ETH/USDT
            if symbol.endswith("USDT") and len(symbol) > 4:
                unified = f"{symbol[:-4]}/USDT"
            else:
                unified = symbol
        if exchange_id in {"binanceusdm", "binance"} and ":" not in unified and unified.endswith("/USDT"):
            # perpetual linear
            try:
                markets = ex.load_markets()
                perp = f"{unified}:USDT"
                if perp in markets:
                    unified = perp
            except ccxt.BaseError as exc:
                logger.debug("GA market metadata unavailable for %s: %s", unified, exc)
        raw = ex.fetch_ohlcv(unified, timeframe=timeframe, limit=limit)
        return [Candle(int(r[0]), float(r[1]), float(r[2]), float(r[3]), float(r[4]), float(r[5])) for r in raw]
    finally:
        if hasattr(ex, "close"):
            try:
                ex.close()
            except ccxt.BaseError as exc:
                logger.debug("GA CCXT client close failed: %s", exc)


def load_universe_packs(
    *,
    cache_dir: Path,
    market_source: str,
    max_symbols: int,
    lookback_bars: int,
    symbols: Sequence[str] | None = None,
    quote_vol_default: float = 1_000_000.0,
) -> tuple[MarketPacks, list[tuple[str, float]]]:
    """Build feature packs for GA. Returns (packs, symbol_vol_pairs)."""
    source = (market_source or "cache").strip().lower()
    selected: list[tuple[str, float]] = []

    if symbols:
        selected = [(s.upper().replace("/", "").replace("-", ""), quote_vol_default) for s in symbols]
        if max_symbols > 0:
            selected = selected[:max_symbols]
    elif source == "cache":
        cached = list_cache_symbols(cache_dir)
        if not cached:
            raise FileNotFoundError(
                f"No cache files in {cache_dir}. Place {{SYMBOL}}_15m.json or set GA_MARKET_SOURCE."
            )
        if max_symbols > 0:
            cached = cached[:max_symbols]
        selected = [(s, quote_vol_default) for s in cached]
    elif source in {"binance_fapi", "binance"}:
        selected = exchange_symbols_binance(max_symbols=max_symbols)
    elif source == "ccxt":
        # Fall back to a small default universe; caller should pass symbols for ccxt.
        defaults = ["BTCUSDT", "ETHUSDT", "SOLUSDT", "XRPUSDT", "BNBUSDT"]
        if max_symbols > 0:
            defaults = defaults[:max_symbols]
        selected = [(s, quote_vol_default) for s in defaults]
    else:
        raise ValueError(f"Unsupported GA_MARKET_SOURCE: {market_source}")

    packs: MarketPacks = {}
    loaded: list[tuple[str, float]] = []
    for sym, qv in selected:
        candles: list[Candle] | None = None
        # Always prefer local cache when present (offline-friendly).
        candles = load_cache_candles(cache_dir, sym, lookback_bars)
        if candles is None:
            try:
                if source in {"binance_fapi", "binance"}:
                    candles = fetch_klines_binance(sym, "15m", lookback_bars)
                elif source == "ccxt":
                    candles = fetch_klines_ccxt(sym, "15m", lookback_bars)
                elif source == "cache":
                    logger.warning("cache miss for %s", sym)
                    continue
                else:
                    candles = fetch_klines_binance(sym, "15m", lookback_bars)
            except Exception as exc:  # noqa: BLE001
                logger.warning("skip %s: %s", sym, exc)
                continue
        if not candles or len(candles) < 150:
            logger.warning("skip %s: insufficient bars (%s)", sym, 0 if not candles else len(candles))
            continue
        packs[sym] = build_symbol_pack(sym, candles, qv, CISD_LENS)
        loaded.append((sym, qv))
        # Persist fetched series for reuse
        if source != "cache":
            try:
                cache_dir.mkdir(parents=True, exist_ok=True)
                payload = [
                    {
                        "timestamp": c.ts,
                        "open": c.o,
                        "high": c.h,
                        "low": c.low,
                        "close": c.c,
                        "volume": c.v,
                    }
                    for c in candles
                ]
                (cache_dir / f"{sym}_15m.json").write_text(json.dumps(payload), encoding="utf-8")
            except Exception as exc:  # noqa: BLE001
                logger.debug("cache write failed for %s: %s", sym, exc)

    if not loaded:
        raise RuntimeError("No market data loaded for GA optimize")
    return packs, loaded
