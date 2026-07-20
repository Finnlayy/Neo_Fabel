"""Paper performance metrics from local ledger fills and open lots."""

from __future__ import annotations

from decimal import Decimal
from typing import Any


def _d(value: Any) -> Decimal:
    if isinstance(value, Decimal):
        return value
    return Decimal(str(value or "0"))


def _positions_from_lots(lots: dict[str, list[dict[str, Any]]], mark_prices: dict[str, Decimal]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for pair, rows in lots.items():
        vol = sum(_d(r.get("volume")) for r in rows)
        if vol <= 0:
            continue
        cost = sum(_d(r.get("volume")) * _d(r.get("unit_cost")) for r in rows)
        mark = mark_prices.get(pair, _d(rows[-1].get("unit_cost") if rows else 0))
        market_value = vol * mark
        unrealized = market_value - cost
        out.append(
            {
                "pair": pair,
                "market_type": "spot",
                "volume": format(vol, "f"),
                "avg_entry": format(cost / vol if vol else Decimal("0"), "f"),
                "mark_price": format(mark, "f"),
                "market_value_usd": format(market_value, "f"),
                "cost_basis_usd": format(cost, "f"),
                "unrealized_pnl_usd": format(unrealized, "f"),
            }
        )
    out.sort(key=lambda r: r["pair"])
    return out


def _equity_curve(
    fills: list[dict[str, Any]],
    starting_balance: Decimal,
    mark_prices: dict[str, Decimal],
    lots: dict[str, list[dict[str, Any]]],
) -> list[dict[str, Any]]:
    """Replay fills to build equity snapshots (usd cash + marked positions)."""
    cash = starting_balance
    open_lots: dict[str, list[dict[str, str]]] = {}
    curve: list[dict[str, Any]] = [
        {"time": None, "equity_usd": format(starting_balance, "f"), "event": "start"},
    ]

    for fill in sorted(fills, key=lambda f: str(f.get("time") or "")):
        pair = str(fill.get("pair") or "")
        side = str(fill.get("side") or "buy").lower()
        vol = _d(fill.get("volume"))
        price = _d(fill.get("price"))
        fee = _d(fill.get("fee"))
        realized = _d(fill.get("realized_pnl"))
        t = fill.get("time")

        if side == "buy":
            cash -= vol * price + fee
            rows = open_lots.setdefault(pair, [])
            unit_cost = (vol * price + fee) / vol if vol else Decimal("0")
            rows.append({"volume": format(vol, "f"), "unit_cost": format(unit_cost, "f")})
        else:
            cash += vol * price - fee
            remaining = vol
            rows = open_lots.get(pair, [])
            while remaining > 0 and rows:
                lot = rows[0]
                lot_vol = _d(lot.get("volume"))
                take = min(lot_vol, remaining)
                lot_vol -= take
                remaining -= take
                if lot_vol <= 0:
                    rows.pop(0)
                else:
                    lot["volume"] = format(lot_vol, "f")

        position_value = Decimal("0")
        for p, p_rows in open_lots.items():
            p_vol = sum(_d(r.get("volume")) for r in p_rows)
            mark = mark_prices.get(p, price if p == pair else Decimal("0"))
            position_value += p_vol * mark

        equity = cash + position_value
        curve.append(
            {
                "time": t,
                "equity_usd": format(equity, "f"),
                "cash_usd": format(cash, "f"),
                "realized_pnl_usd": format(realized, "f"),
                "event": f"{side} {pair}",
            }
        )
    return curve


def _max_drawdown(curve: list[dict[str, Any]]) -> Decimal:
    peak = Decimal("0")
    max_dd = Decimal("0")
    for point in curve:
        eq = _d(point.get("equity_usd"))
        if eq > peak:
            peak = eq
        if peak > 0:
            dd = (peak - eq) / peak
            if dd > max_dd:
                max_dd = dd
    return max_dd


def _by_symbol(fills: list[dict[str, Any]]) -> list[dict[str, Any]]:
    buckets: dict[str, dict[str, Any]] = {}
    for fill in fills:
        pair = str(fill.get("pair") or "UNKNOWN")
        side = str(fill.get("side") or "").lower()
        bucket = buckets.setdefault(
            pair,
            {
                "pair": pair,
                "fills": 0,
                "buy_volume": Decimal("0"),
                "sell_volume": Decimal("0"),
                "realized_pnl_usd": Decimal("0"),
                "fees_usd": Decimal("0"),
            },
        )
        bucket["fills"] += 1
        vol = _d(fill.get("volume"))
        if side == "buy":
            bucket["buy_volume"] += vol
        else:
            bucket["sell_volume"] += vol
        bucket["realized_pnl_usd"] += _d(fill.get("realized_pnl"))
        bucket["fees_usd"] += _d(fill.get("fee"))

    out: list[dict[str, Any]] = []
    for pair in sorted(buckets):
        b = buckets[pair]
        out.append(
            {
                "pair": pair,
                "fills": b["fills"],
                "buy_volume": format(b["buy_volume"], "f"),
                "sell_volume": format(b["sell_volume"], "f"),
                "realized_pnl_usd": format(b["realized_pnl_usd"], "f"),
                "fees_usd": format(b["fees_usd"], "f"),
            }
        )
    return out


def _futures_positions(
    positions: dict[str, dict[str, Any]],
    mark_prices: dict[str, Decimal],
) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for pair, pos in positions.items():
        contracts = _d(pos.get("contracts"))
        if contracts <= 0:
            continue
        entry = _d(pos.get("entry_price"))
        side = str(pos.get("side") or "long").lower()
        mark = mark_prices.get(pair, entry)
        sign = Decimal("1") if side == "long" else Decimal("-1")
        notional = contracts * mark
        cost = contracts * entry
        unrealized = (mark - entry) * contracts * sign
        out.append(
            {
                "pair": pair,
                "market_type": "futures",
                "side": side,
                "volume": format(contracts, "f"),
                "leverage": int(pos.get("leverage") or 1),
                "avg_entry": format(entry, "f"),
                "mark_price": format(mark, "f"),
                "market_value_usd": format(notional, "f"),
                "cost_basis_usd": format(cost, "f"),
                "unrealized_pnl_usd": format(unrealized, "f"),
                "initial_margin_usd": format(_d(pos.get("initial_margin")), "f"),
            }
        )
    out.sort(key=lambda r: r["pair"])
    return out


def build_futures_performance(
    *,
    futures_book: dict[str, Any],
    mark_prices: dict[str, Decimal],
    source: str = "local-paper-ledger",
    fee_model: str = "kraken_pro_tier5",
) -> dict[str, Any]:
    starting = _d(futures_book.get("starting_margin_usd"))
    margin = _d(futures_book.get("margin_balance_usd"))
    positions_raw: dict[str, dict[str, Any]] = futures_book.get("positions") or {}
    fills: list[dict[str, Any]] = list(futures_book.get("fills") or [])

    positions = _futures_positions(positions_raw, mark_prices)
    unrealized = sum(_d(p["unrealized_pnl_usd"]) for p in positions)
    equity = margin + unrealized
    realized_total = sum(_d(f.get("realized_pnl")) for f in fills)
    fees_total = sum(_d(f.get("fee")) for f in fills)
    closed = [f for f in fills if _d(f.get("realized_pnl")) != 0]
    wins = sum(1 for f in closed if _d(f.get("realized_pnl")) > 0)
    losses = sum(1 for f in closed if _d(f.get("realized_pnl")) < 0)
    closed_rounds = wins + losses

    return {
        "source": source,
        "fee_model": fee_model,
        "starting_margin_usd": format(starting, "f"),
        "margin_balance_usd": format(margin, "f"),
        "equity_usd": format(equity, "f"),
        "position_value_usd": format(sum(_d(p["market_value_usd"]) for p in positions), "f"),
        "realized_pnl_usd": format(realized_total, "f"),
        "unrealized_pnl_usd": format(unrealized, "f"),
        "total_pnl_usd": format(realized_total + unrealized, "f"),
        "fees_paid_usd": format(fees_total, "f"),
        "win_rate": round(wins / closed_rounds, 4) if closed_rounds else None,
        "wins": wins,
        "losses": losses,
        "closed_rounds": closed_rounds,
        "fill_count": len(fills),
        "max_drawdown_pct": "0",
        "positions": positions,
        "by_symbol": _by_symbol(fills),
        "equity_curve": [],
        "fills": list(reversed(fills[-200:])),
    }


def build_combined_performance(
    *,
    state: dict[str, Any],
    mark_prices: dict[str, Decimal],
    source: str = "local-paper-ledger",
    fee_model: str = "kraken_pro_tier5",
) -> dict[str, Any]:
    version = int(state.get("version", 1))
    if version < 2:
        spot_only = build_performance_snapshot(
            state=state,
            mark_prices=mark_prices,
            source=source,
            fee_model=fee_model,
        )
        return {
            **spot_only,
            "ledger_version": 1,
            "spot": spot_only,
            "futures": None,
            "combined_equity_usd": spot_only["equity_usd"],
        }

    spot_book = state.get("spot") or {}
    futures_book = state.get("futures") or {}
    spot_marks = {k: v for k, v in mark_prices.items() if k in (spot_book.get("lots") or {})}
    fut_marks = {k: v for k, v in mark_prices.items() if k in (futures_book.get("positions") or {})}

    spot_perf = build_performance_snapshot(
        state={
            "starting_balance_usd": spot_book.get("starting_balance_usd"),
            "usd_balance": spot_book.get("usd_balance"),
            "lots": spot_book.get("lots") or {},
            "fills": spot_book.get("fills") or [],
        },
        mark_prices=spot_marks,
        source=source,
        fee_model=fee_model,
    )
    futures_perf = build_futures_performance(
        futures_book=futures_book,
        mark_prices=fut_marks,
        source=source,
        fee_model=fee_model,
    )
    combined_equity = _d(spot_perf["equity_usd"]) + _d(futures_perf["equity_usd"])
    all_fills = list(spot_book.get("fills") or []) + list(futures_book.get("fills") or [])
    realized_total = _d(spot_perf["realized_pnl_usd"]) + _d(futures_perf["realized_pnl_usd"])
    unrealized_total = _d(spot_perf["unrealized_pnl_usd"]) + _d(futures_perf["unrealized_pnl_usd"])

    return {
        "source": source,
        "fee_model": fee_model,
        "ledger_version": 2,
        "starting_balance_usd": spot_perf["starting_balance_usd"],
        "usd_balance": spot_perf["usd_balance"],
        "starting_margin_usd": futures_perf["starting_margin_usd"],
        "margin_balance_usd": futures_perf["margin_balance_usd"],
        "equity_usd": format(combined_equity, "f"),
        "combined_equity_usd": format(combined_equity, "f"),
        "position_value_usd": format(
            _d(spot_perf["position_value_usd"]) + _d(futures_perf["position_value_usd"]),
            "f",
        ),
        "realized_pnl_usd": format(realized_total, "f"),
        "unrealized_pnl_usd": format(unrealized_total, "f"),
        "total_pnl_usd": format(realized_total + unrealized_total, "f"),
        "fees_paid_usd": format(
            _d(spot_perf["fees_paid_usd"]) + _d(futures_perf["fees_paid_usd"]),
            "f",
        ),
        "win_rate": spot_perf["win_rate"],
        "wins": spot_perf["wins"] + futures_perf["wins"],
        "losses": spot_perf["losses"] + futures_perf["losses"],
        "closed_rounds": spot_perf["closed_rounds"] + futures_perf["closed_rounds"],
        "fill_count": len(all_fills),
        "max_drawdown_pct": spot_perf["max_drawdown_pct"],
        "positions": spot_perf["positions"] + futures_perf["positions"],
        "by_symbol": _by_symbol(all_fills),
        "equity_curve": spot_perf["equity_curve"],
        "fills": list(reversed(sorted(all_fills, key=lambda f: str(f.get("time") or ""))[-200:])),
        "spot": spot_perf,
        "futures": futures_perf,
    }


def build_performance_snapshot(
    *,
    state: dict[str, Any],
    mark_prices: dict[str, Decimal],
    source: str = "local-paper-ledger",
    fee_model: str = "kraken_pro_tier5",
) -> dict[str, Any]:
    starting = _d(state.get("starting_balance_usd"))
    cash = _d(state.get("usd_balance"))
    lots: dict[str, list[dict[str, Any]]] = state.get("lots") or {}
    fills: list[dict[str, Any]] = list(state.get("fills") or [])

    positions = _positions_from_lots(lots, mark_prices)
    position_value = sum(_d(p["market_value_usd"]) for p in positions)
    cost_basis = sum(_d(p["cost_basis_usd"]) for p in positions)
    unrealized = position_value - cost_basis
    equity = cash + position_value

    realized_total = sum(_d(f.get("realized_pnl")) for f in fills)
    fees_total = sum(_d(f.get("fee")) for f in fills)
    sell_fills = [f for f in fills if str(f.get("side")).lower() == "sell"]
    wins = sum(1 for f in sell_fills if _d(f.get("realized_pnl")) > 0)
    losses = sum(1 for f in sell_fills if _d(f.get("realized_pnl")) < 0)
    closed_rounds = wins + losses

    curve = _equity_curve(fills, starting, mark_prices, lots)
    max_dd = _max_drawdown(curve)

    return {
        "source": source,
        "fee_model": fee_model,
        "starting_balance_usd": format(starting, "f"),
        "usd_balance": format(cash, "f"),
        "equity_usd": format(equity, "f"),
        "position_value_usd": format(position_value, "f"),
        "realized_pnl_usd": format(realized_total, "f"),
        "unrealized_pnl_usd": format(unrealized, "f"),
        "total_pnl_usd": format(realized_total + unrealized, "f"),
        "fees_paid_usd": format(fees_total, "f"),
        "win_rate": round(wins / closed_rounds, 4) if closed_rounds else None,
        "wins": wins,
        "losses": losses,
        "closed_rounds": closed_rounds,
        "fill_count": len(fills),
        "max_drawdown_pct": format(max_dd * 100, "f"),
        "positions": positions,
        "by_symbol": _by_symbol(fills),
        "equity_curve": curve[-120:],
        "fills": list(reversed(fills[-200:])),
    }
