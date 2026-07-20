"""Academy drill market data — tvremix MCP primary, fixture fallback (paper/training only).

Datei: drill_market.py
Zweck: OHLCV/quote/technicals/structure for Academy drills without live trading.
Erstellt: 2026-07-20 | Version: 1.0
Abhaengig: tvremix_client, settings, academy fixtures
"""

from __future__ import annotations

import json
import logging
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from backend.app.settings import Settings, get_settings

logger = logging.getLogger("neo_fabel.academy.drill_market")

FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures"
_FIXTURE_CACHE: dict[str, Any] | None = None


def _load_fixture_pack() -> dict[str, Any]:
    global _FIXTURE_CACHE
    if _FIXTURE_CACHE is not None:
        return _FIXTURE_CACHE
    path = FIXTURES_DIR / "market_tape.json"
    _FIXTURE_CACHE = json.loads(path.read_text(encoding="utf-8"))
    return _FIXTURE_CACHE


def resolve_academy_source(settings: Settings | None = None) -> str:
    """Preferred live source label when ACADEMY_DRILL_LIVE_DATA is on."""
    cfg = settings or get_settings()
    if not cfg.academy_drill_live_data:
        return "fixture"
    has_key = bool((cfg.tvremix_api_key or "").strip())
    if cfg.tvremix_enabled and has_key:
        return "tvremix"
    return "ccxt"


def provenance(
    *,
    primary: str,
    tools: list[str],
    fallback_used: bool = False,
    symbol_tv: str | None = None,
    symbol_neo: str = "BTCUSD",
    secondary_sources: list[str] | None = None,
) -> dict[str, Any]:
    return {
        "primary": primary,
        "fallback_used": fallback_used,
        "tools": tools,
        "fetched_at": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
        "symbol_tv": symbol_tv or "BINANCE:BTCUSDT",
        "symbol_neo": symbol_neo,
        "secondary_sources": secondary_sources or [],
    }


def fixture_candles(count: int = 60) -> list[dict[str, Any]]:
    pack = _load_fixture_pack()
    base = list(pack.get("candles") or [])
    if not base:
        return []
    out: list[dict[str, Any]] = []
    while len(out) < count:
        for bar in base:
            cloned = dict(bar)
            if out:
                cloned["timestamp"] = int(out[-1]["timestamp"]) + 300
                drift = 1.0 + ((len(out) % 7) - 3) * 0.0004
                for key in ("open", "high", "low", "close"):
                    cloned[key] = float(cloned[key]) * drift
            out.append(cloned)
            if len(out) >= count:
                break
    return out[:count]


def fixture_quote() -> dict[str, Any]:
    return dict(_load_fixture_pack().get("quote") or {"last": 65000.0, "change_pct": 0.0})


def fixture_pack() -> dict[str, Any]:
    return dict(_load_fixture_pack())


def candles_to_ohlcva(candles: list[dict[str, Any]]) -> list[list[float]]:
    rows: list[list[float]] = []
    for bar in candles:
        o = float(bar["open"])
        h = float(bar["high"])
        l = float(bar["low"])
        c = float(bar["close"])
        v = float(bar.get("volume") or 0.0)
        typical = (o + h + l + c) / 4.0
        rows.append([o, h, l, c, v, v * typical])
    return rows


async def fetch_drill_candles(
    pair: str = "BTCUSD",
    *,
    interval: str = "5m",
    count: int = 60,
    settings: Settings | None = None,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Return (candles, provenance). Never raises — always falls back to fixtures."""
    cfg = settings or get_settings()
    source = resolve_academy_source(cfg)
    tools: list[str] = []
    if source == "tvremix":
        try:
            from backend.app.integrations.tvremix_client import TvremixClient
            from backend.app.signals.engine.market_source import bars_to_candles

            client = TvremixClient(cfg)
            raw = await client.fetch_ohlcv_raw(pair, interval=interval, count=count)
            candles = bars_to_candles(raw)
            tools.append("get_ohlcv")
            if candles:
                return candles, provenance(
                    primary="tvremix",
                    tools=tools,
                    symbol_neo=pair,
                )
        except Exception as exc:  # noqa: BLE001
            logger.warning("academy tvremix candles failed (%s); fallback", exc)
    if source in {"tvremix", "ccxt"}:
        try:
            from backend.app.signals.engine.market_source import fetch_candles as engine_fetch

            candles = await engine_fetch(pair, settings=cfg, count=count)
            if candles:
                return candles, provenance(
                    primary="ccxt" if source != "tvremix" else "tvremix",
                    tools=tools or ["ccxt_ohlcv"],
                    fallback_used=source == "tvremix",
                    symbol_neo=pair,
                )
        except Exception as exc:  # noqa: BLE001
            logger.warning("academy ccxt candles failed (%s); using fixture", exc)
    return fixture_candles(count), provenance(
        primary="fixture",
        tools=["fixture_pack"],
        fallback_used=True,
        symbol_neo=pair,
    )


async def fetch_drill_quote(
    symbol: str = "BTCUSD",
    *,
    settings: Settings | None = None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    cfg = settings or get_settings()
    if resolve_academy_source(cfg) == "tvremix":
        try:
            from backend.app.integrations.tvremix_client import TvremixClient

            client = TvremixClient(cfg)
            quote = await client.fetch_quote(symbol)
            if quote:
                return quote, provenance(primary="tvremix", tools=["get_quote"], symbol_neo=symbol)
        except Exception as exc:  # noqa: BLE001
            logger.warning("academy tvremix quote failed (%s)", exc)
    return fixture_quote(), provenance(
        primary="fixture", tools=["fixture_pack"], fallback_used=True, symbol_neo=symbol
    )


async def fetch_drill_technicals(
    symbol: str = "BTCUSD",
    *,
    interval: str = "5m",
    settings: Settings | None = None,
) -> tuple[dict[str, Any] | None, dict[str, Any]]:
    cfg = settings or get_settings()
    if resolve_academy_source(cfg) == "tvremix":
        try:
            from backend.app.integrations.tvremix_client import TvremixClient

            client = TvremixClient(cfg)
            data = await client.fetch_technicals(symbol, interval=interval)
            if data:
                return data, provenance(
                    primary="tvremix", tools=["get_technicals"], symbol_neo=symbol
                )
        except Exception as exc:  # noqa: BLE001
            logger.warning("academy tvremix technicals failed (%s)", exc)
    pack = fixture_pack()
    return (
        {"rating": pack.get("technicals_rating"), "interval": interval},
        provenance(primary="fixture", tools=["fixture_pack"], fallback_used=True, symbol_neo=symbol),
    )


async def fetch_drill_structure(
    symbol: str = "BTCUSD",
    *,
    interval: str = "5m",
    settings: Settings | None = None,
) -> tuple[dict[str, Any] | None, dict[str, Any]]:
    """SMC/swing levels proxy — tvremix has no L2 order book."""
    cfg = settings or get_settings()
    if resolve_academy_source(cfg) == "tvremix":
        try:
            from backend.app.integrations.tvremix_client import TvremixClient

            client = TvremixClient(cfg)
            data = await client.fetch_structure_levels(symbol, interval=interval)
            if data:
                return data, provenance(
                    primary="tvremix",
                    tools=["analyze_smc_tool", "analyze_swing_tool"],
                    symbol_neo=symbol,
                )
        except Exception as exc:  # noqa: BLE001
            logger.warning("academy tvremix structure failed (%s)", exc)
    pack = fixture_pack()
    return (
        dict(pack.get("levels_proxy") or {}),
        provenance(primary="fixture", tools=["fixture_pack"], fallback_used=True, symbol_neo=symbol),
    )


async def fetch_drill_orderbook_secondary(
    pair: str = "BTCUSD",
    *,
    count: int = 12,
) -> tuple[dict[str, Any] | None, list[str]]:
    """Labeled Neo public L2 — never private Kraken."""
    try:
        from backend.app.main import crypto_orderbook_data

        data, source = await crypto_orderbook_data(pair, count=count)
        if isinstance(data, dict) and (data.get("bids") or data.get("asks")):
            return {
                "source": "neo_kraken_public_l2",
                "provider": source,
                "bids": (data.get("bids") or [])[:count],
                "asks": (data.get("asks") or [])[:count],
            }, ["neo_kraken_public_l2"]
    except Exception as exc:  # noqa: BLE001
        logger.warning("academy secondary orderbook failed (%s)", exc)
    return None, []
