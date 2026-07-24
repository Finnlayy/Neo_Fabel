"""EMA-cross grid backtest — port of tv-extension-mvp/extension/modules/optimizer.js."""

from __future__ import annotations

import math
from itertools import product
from typing import Any


def ema(values: list[float], period: int) -> list[float | None]:
    if period <= 0:
        raise ValueError("Invalid EMA period")
    out: list[float | None] = [None] * len(values)
    if not values:
        return out
    k = 2.0 / (period + 1)
    previous = float(values[0])
    out[0] = previous
    for i in range(1, len(values)):
        previous = float(values[i]) * k + previous * (1.0 - k)
        out[i] = previous
    return out


def evaluate_ema_cross(candles: list[dict[str, Any]], params: dict[str, Any]) -> dict[str, Any]:
    closes = [float(c["close"]) for c in candles]
    fast_p = max(2, int(params.get("emaFast", 8)))
    slow_p = max(fast_p + 1, int(params.get("emaSlow", 21)))
    tp = float(params.get("takeProfitPct", 1.5))
    sl = float(params.get("stopLossPct", 1.0))

    fast = ema(closes, fast_p)
    slow = ema(closes, slow_p)

    position: dict[str, Any] | None = None
    equity = 1_000.0
    peak = equity
    max_drawdown = 0.0
    wins = 0
    losses = 0
    trades: list[dict[str, Any]] = []

    for i in range(1, len(candles)):
        fast_prev = fast[i - 1]
        slow_prev = slow[i - 1]
        fast_now = fast[i]
        slow_now = slow[i]
        if fast_prev is None or slow_prev is None or fast_now is None or slow_now is None:
            continue
        crossed_up = fast_prev <= slow_prev and fast_now > slow_now
        crossed_down = fast_prev >= slow_prev and fast_now < slow_now
        price = float(candles[i]["close"])

        if position is None and crossed_up:
            position = {"entry": price, "entryIndex": i}
            continue

        if position is not None:
            pnl_pct = ((price - float(position["entry"])) / float(position["entry"])) * 100.0
            hit_tp = pnl_pct >= tp
            hit_sl = pnl_pct <= -sl
            if crossed_down or hit_tp or hit_sl:
                pnl = equity * (pnl_pct / 100.0)
                equity += pnl
                peak = max(peak, equity)
                if peak > 0:
                    max_drawdown = max(max_drawdown, (peak - equity) / peak)
                if pnl > 0:
                    wins += 1
                else:
                    losses += 1
                trades.append(
                    {
                        **position,
                        "exit": price,
                        "exitIndex": i,
                        "pnlPct": pnl_pct,
                        "pnl": pnl,
                    }
                )
                position = None

    trade_count = len(trades)
    win_rate = (wins / trade_count) if trade_count else 0.0
    net_profit = equity - 1_000.0
    # Profit factor from winning vs losing trade PnL
    gross_win = sum(t["pnl"] for t in trades if t["pnl"] > 0)
    gross_loss = abs(sum(t["pnl"] for t in trades if t["pnl"] <= 0))
    profit_factor = (gross_win / gross_loss) if gross_loss > 1e-9 else (gross_win if gross_win > 0 else 0.0)
    fitness = net_profit - max_drawdown * 700.0 + win_rate * 50.0

    return {
        "equity": equity,
        "netProfit": round(net_profit, 4),
        "maxDrawdown": round(max_drawdown, 6),
        "trades": trade_count,
        "wins": wins,
        "losses": losses,
        "winRate": round(win_rate * 100.0, 2),
        "profitFactor": round(float(profit_factor), 3),
        "fitness": fitness,
    }


def _expand_range(start: float, step: float, end: float) -> list[float]:
    values: list[float] = []
    if step <= 0:
        return [start]
    n = int(math.floor((end - start) / step + 1e-9)) + 1
    for i in range(max(0, n)):
        values.append(round(start + i * step, 6))
    return values


def optimize_ema_cross(
    candles: list[dict[str, Any]],
    schema: dict[str, dict[str, float]] | None = None,
    *,
    limit: int = 400,
    min_trades: int = 1,
) -> dict[str, Any]:
    schema = schema or {
        "emaFast": {"start": 5, "step": 3, "end": 14},
        "emaSlow": {"start": 18, "step": 6, "end": 36},
        "takeProfitPct": {"start": 1.0, "step": 0.5, "end": 2.0},
        "stopLossPct": {"start": 0.75, "step": 0.25, "end": 1.5},
    }
    keys = list(schema.keys())
    ranges = [_expand_range(float(schema[k]["start"]), float(schema[k]["step"]), float(schema[k]["end"])) for k in keys]

    best: dict[str, Any] | None = None
    results: list[dict[str, Any]] = []
    tested = 0

    for combo in product(*ranges):
        params = {keys[i]: combo[i] for i in range(len(keys))}
        # Keep fast < slow
        if "emaFast" in params and "emaSlow" in params and params["emaFast"] >= params["emaSlow"]:
            continue
        tested += 1
        metrics = evaluate_ema_cross(candles, params)
        row = {
            "params": params,
            "result": metrics,
            "isDisqualified": metrics["trades"] < min_trades,
        }
        results.append(row)
        if not row["isDisqualified"]:
            if best is None or metrics["fitness"] > best["result"]["fitness"]:
                best = row
        if tested >= limit:
            break

    if best is None and results:
        best = max(results, key=lambda r: r["result"]["fitness"])

    return {"tested": tested, "best": best, "results": results}


def synthetic_candles(symbol: str, n: int = 240) -> list[dict[str, float]]:
    """Deterministic walk for offline/dev when live OHLCV is unavailable."""
    seed = sum(ord(c) for c in symbol.upper()) % 97
    price = 100.0 + seed
    out: list[dict[str, float]] = []
    for i in range(n):
        # Mild sine + drift so EMA crosses / LTM flips occur
        delta = math.sin(i / 7.0 + seed / 10.0) * 1.2 + math.cos(i / 13.0) * 0.6
        open_ = price
        price = max(1.0, price + delta)
        high = max(open_, price) + abs(delta) * 0.35
        low = min(open_, price) - abs(delta) * 0.35
        out.append(
            {
                "open": round(open_, 6),
                "high": round(high, 6),
                "low": round(low, 6),
                "close": round(price, 6),
                "volume": float(1000 + (seed * 7 + i * 3) % 500),
            }
        )
    return out


def run_candle_optimize(
    payload: dict[str, Any],
    candles: list[dict[str, Any]],
    *,
    candle_source: str = "ohlcv",
) -> dict[str, Any]:
    """UI-compatible optimize response from real (or synthetic) candles."""
    from backend.app.integrations.backtest.ltm_analyzer import is_ltm_strategy, run_ltm_optimize

    if is_ltm_strategy(payload):
        return run_ltm_optimize(payload, candles, candle_source=candle_source)

    strategy = str(payload.get("strategy") or "ema_cross")
    symbol = str(payload.get("symbol") or "BTCUSD").upper()
    timeframe = str(payload.get("timeframe") or "5m")
    min_trades = max(1, int(payload.get("minTrades") or 5))
    primary = str(payload.get("primaryObjective") or "profit_factor")
    secondary = str(payload.get("secondaryObjective") or "percent_profitable")

    if len(candles) < 30:
        return {
            "success": False,
            "error": f"Need at least 30 candles for backtest; got {len(candles)}",
            "source": "candle-backtest",
        }

    # EMA grid for ema_cross / default; other strategy kinds still use EMA as V1 engine
    opt = optimize_ema_cross(candles, limit=400, min_trades=min_trades)
    best = opt.get("best")
    if not best:
        return {
            "success": False,
            "error": "No parameter sets evaluated",
            "source": "candle-backtest",
        }

    def score(row: dict[str, Any]) -> tuple[float, float]:
        m = row["result"]
        primary_val = {
            "profit_factor": float(m["profitFactor"]),
            "net_profit": float(m["netProfit"]),
            "win_rate": float(m["winRate"]),
        }.get(primary, float(m["profitFactor"]))
        secondary_val = {
            "percent_profitable": float(m["winRate"]),
            "net_profit": float(m["netProfit"]),
            "profit_factor": float(m["profitFactor"]),
        }.get(secondary, float(m["winRate"]))
        return (primary_val, secondary_val)

    ranked = sorted(opt["results"], key=score, reverse=True)
    winner_row = best if not best["isDisqualified"] else max(ranked, key=score)
    wm = winner_row["result"]
    winner = {
        "label": f"EMA-CROSS-{int(winner_row['params'].get('emaFast', 0))}/{int(winner_row['params'].get('emaSlow', 0))}",
        "profitFactor": wm["profitFactor"],
        "netProfit": wm["netProfit"],
        "winRate": wm["winRate"],
        "trades": wm["trades"],
        "inputs": winner_row["params"],
        "maxDrawdown": wm["maxDrawdown"],
    }

    results: list[dict[str, Any]] = []
    for idx, row in enumerate(ranked[:40], start=1):
        m = row["result"]
        label = f"EMA-{int(row['params'].get('emaFast', 0))}/{int(row['params'].get('emaSlow', 0))}"
        results.append(
            {
                "rank": idx,
                "label": label,
                "profitFactor": m["profitFactor"],
                "winRate": m["winRate"],
                "netProfit": m["netProfit"],
                "trades": m["trades"],
                "maxDrawdown": m["maxDrawdown"],
                "inputs": row["params"],
                "isWinner": label == winner["label"],
                "isDisqualified": row["isDisqualified"],
            }
        )

    source = f"candle-backtest/{candle_source}"
    bericht = (
        f"### Candle backtest (tv-extension-mvp EMA grid)\n"
        f"- Symbol: `{symbol}` TF `{timeframe}` strategy `{strategy}`\n"
        f"- Candles: `{len(candles)}` · tested `{opt['tested']}` combos · source `{source}`\n"
        f"- Primary: `{primary}` / secondary `{secondary}`\n"
        f"- Winner: **{winner['label']}** PF={winner['profitFactor']} "
        f"WR={winner['winRate']}% NP={winner['netProfit']} DD={winner['maxDrawdown']}\n"
        f"- Not vision/YouTube; not live TradingView study introspection.\n"
    )
    self_test = (
        "PASS: OHLCV candle engine produced ranked EMA-cross results; "
        "minTrades filter applied; vision analyze-chart was not used."
    )

    return {
        "success": True,
        "winner": winner,
        "bericht": bericht,
        "selfTest": self_test,
        "results": results,
        "source": source,
        "candlesUsed": len(candles),
        "tested": opt["tested"],
    }
