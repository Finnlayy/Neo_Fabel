"""Unified open positions — paper ledger lots and Kraken live balances."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from decimal import Decimal, InvalidOperation
from typing import Any

from backend.app.integrations.kraken_cli import KrakenCli, KrakenCliError

FIAT_ASSETS = frozenset({"USD", "ZUSD", "EUR", "ZEUR", "USDT", "USDC", "GBP", "CAD", "JPY", "CHF", "AUD"})
ASSET_TO_PAIR = {
    "BTC": "BTCUSD",
    "XBT": "BTCUSD",
    "ETH": "ETHUSD",
    "SOL": "SOLUSD",
    "XRP": "XRPUSD",
    "ADA": "ADAUSD",
    "DOGE": "DOGEUSD",
    "DOT": "DOTUSD",
    "LINK": "LINKUSD",
    "LTC": "LTCUSD",
    "MATIC": "MATICUSD",
    "POL": "POLUSD",
    "AVAX": "AVAXUSD",
    "BCH": "BCHUSD",
}


def _d(value: Any) -> Decimal:
    if isinstance(value, Decimal):
        return value
    try:
        return Decimal(str(value or "0"))
    except InvalidOperation:
        return Decimal(0)


def asset_to_pair(asset: str) -> str:
    key = asset.strip().upper()
    if key.endswith("USD") and len(key) > 3:
        return key.replace("/", "").replace("-", "")
    mapped = ASSET_TO_PAIR.get(key)
    if mapped:
        return mapped
    return f"{key}USD"


def parse_live_balances(payload: dict[str, Any] | None) -> list[dict[str, Any]]:
    """Extract non-fiat holdings from Kraken CLI balance JSON."""
    if not payload or not isinstance(payload, dict):
        return []

    rows: list[tuple[str, Decimal]] = []
    for key, value in payload.items():
        if key in {"error", "result", "raw"}:
            continue
        asset = str(key).upper()
        if asset in FIAT_ASSETS:
            continue
        vol = _d(value)
        if vol <= 0:
            continue
        rows.append((asset, vol))

    # Nested result shape
    nested = payload.get("result") or payload.get("balances")
    if isinstance(nested, dict):
        for asset, value in nested.items():
            asset_u = str(asset).upper()
            if asset_u in FIAT_ASSETS:
                continue
            vol = _d(value)
            if vol > 0:
                rows.append((asset_u, vol))

    # De-dupe by asset (prefer nested if duplicate)
    merged: dict[str, Decimal] = {}
    for asset, vol in rows:
        merged[asset] = vol

    out: list[dict[str, Any]] = []
    for asset, vol in sorted(merged.items()):
        pair = asset_to_pair(asset)
        out.append(
            {
                "mode": "live",
                "asset": asset,
                "pair": pair,
                "volume": format(vol, "f"),
                "avg_entry": None,
                "mark_price": None,
                "market_value_usd": None,
                "cost_basis_usd": None,
                "unrealized_pnl_usd": None,
                "source": "kraken-balance",
            }
        )
    return out


def parse_open_orders(payload: dict[str, Any] | None) -> list[dict[str, Any]]:
    if not payload or not isinstance(payload, dict):
        return []
    orders_raw: Any = payload.get("open") or payload.get("orders") or payload.get("result") or payload
    if isinstance(orders_raw, dict):
        items = list(orders_raw.values())
    elif isinstance(orders_raw, list):
        items = orders_raw
    else:
        return []

    out: list[dict[str, Any]] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        raw_descr = item.get("descr")
        descr: dict[str, Any] = raw_descr if isinstance(raw_descr, dict) else {}
        pair = str(item.get("pair") or descr.get("pair") or "UNKNOWN")
        side = str(descr.get("type") or item.get("side") or item.get("type") or "").lower()
        out.append(
            {
                "mode": "live",
                "order_id": str(item.get("txid") or item.get("id") or item.get("refid") or ""),
                "pair": pair.replace("/", "").upper(),
                "side": side,
                "volume": str(item.get("vol") or descr.get("order") or item.get("volume") or ""),
                "price": str(item.get("price") or descr.get("price") or ""),
                "status": str(item.get("status") or "open"),
                "source": "kraken-open-orders",
            }
        )
    return out


async def enrich_with_marks(
    positions: list[dict[str, Any]],
    ticker_fn: Callable[[str], Awaitable[tuple[dict[str, Any], str]]],
) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for row in positions:
        copy = dict(row)
        pair = str(copy.get("pair") or "")
        vol = _d(copy.get("volume"))
        try:
            ticker, _ = await ticker_fn(pair)
            last = ticker.get("last") or ticker.get("price") or ticker.get("close")
            if isinstance(last, list) and last:
                last = last[0]
            mark = _d(last)
        except KrakenCliError:
            mark = Decimal(0)
        copy["mark_price"] = format(mark, "f") if mark > 0 else None
        if mark > 0 and vol > 0:
            mv = vol * mark
            copy["market_value_usd"] = format(mv, "f")
        out.append(copy)
    return out


async def build_positions_snapshot(
    *,
    paper_positions: list[dict[str, Any]],
    cli: KrakenCli,
    ticker_fn: Callable[[str], Awaitable[tuple[dict[str, Any], str]]],
    live_trading_enabled: bool,
    trade_commands_enabled: bool,
) -> dict[str, Any]:
    paper = [{**p, "mode": "paper"} for p in paper_positions]
    live: list[dict[str, Any]] = []
    open_orders: list[dict[str, Any]] = []
    errors: list[dict[str, str]] = []

    # Paper-only: never touch the Kraken binary — missing CLI must not pollute the UI.
    if live_trading_enabled:
        try:
            balance = await cli.balance()
            live = parse_live_balances(balance if isinstance(balance, dict) else None)
            live = await enrich_with_marks(live, ticker_fn)
        except KrakenCliError as exc:
            errors.append({"source": "live_balance", "category": exc.category, "message": str(exc)})

        try:
            orders = await cli.open_orders()
            open_orders = parse_open_orders(orders if isinstance(orders, dict) else None)
        except KrakenCliError as exc:
            errors.append({"source": "open_orders", "category": exc.category, "message": str(exc)})

    return {
        "paper": paper,
        "live": live,
        "open_orders": open_orders,
        "live_trading_enabled": live_trading_enabled,
        "trade_commands_enabled": trade_commands_enabled,
        "live_close_available": live_trading_enabled and trade_commands_enabled,
        "errors": errors,
        "total_open": len(paper) + len(live),
    }
