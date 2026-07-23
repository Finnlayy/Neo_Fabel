"""Liquidity Trail Matrix (LTM) analyzer — port of Finn Powers / WillyAlgoTrader v1.3 core.

Precision signal engine: ATR trail bands, scored band retests, flip detection,
wick/ATR risk simulation. Visuals / volume-profile boxes stay in Pine.
"""

from __future__ import annotations

import math
from typing import Any

BAND_PRESETS = {
    "Scalping": (2.5, 0.20),
    "Balanced": (4.0, 0.25),
    "Deep Trend": (6.0, 0.30),
}
RISK_PRESETS = {
    "Conservative": (2.5, 1.0, 2.0, 4.0),
    "Balanced": (1.5, 1.0, 2.0, 3.0),
    "Aggressive": (1.0, 1.5, 2.5, 4.0),
    "Scalping": (0.8, 0.8, 1.5, 2.0),
}
FLIP_BAND = {"Fast (Band 2)": 2, "Balanced (Band 3)": 3, "Deep (Band 4)": 4}


def _atr(highs: list[float], lows: list[float], closes: list[float], length: int) -> list[float]:
    n = len(closes)
    out = [0.0] * n
    if n == 0:
        return out
    trs: list[float] = []
    for i in range(n):
        if i == 0:
            trs.append(highs[i] - lows[i])
        else:
            trs.append(
                max(
                    highs[i] - lows[i],
                    abs(highs[i] - closes[i - 1]),
                    abs(lows[i] - closes[i - 1]),
                )
            )
    for i in range(n):
        window = trs[max(0, i - length + 1) : i + 1]
        out[i] = sum(window) / len(window)
    return out


def _ema(values: list[float], period: int) -> list[float]:
    out = [0.0] * len(values)
    if not values:
        return out
    k = 2.0 / (period + 1)
    out[0] = values[0]
    for i in range(1, len(values)):
        out[i] = values[i] * k + out[i - 1] * (1.0 - k)
    return out


def _sma(values: list[float], period: int) -> list[float]:
    out = [0.0] * len(values)
    acc = 0.0
    for i, v in enumerate(values):
        acc += v
        if i >= period:
            acc -= values[i - period]
        denom = min(i + 1, period)
        out[i] = acc / denom
    return out


def _resolve_band(params: dict[str, Any]) -> tuple[float, float]:
    preset = str(params.get("bandPreset") or params.get("Band Width Preset") or "Balanced")
    if preset in BAND_PRESETS:
        return BAND_PRESETS[preset]
    base = float(params.get("baseMult") or params.get("Base Multiplier (×ATR)") or 5.0)
    step = float(params.get("bandStep") or params.get("Band Spacing (proportional step)") or 0.25)
    return base, step


def _resolve_risk(params: dict[str, Any]) -> tuple[float, float, float, float]:
    preset = str(params.get("riskPreset") or params.get("Risk Preset") or "Balanced")
    if preset in RISK_PRESETS and preset != "Custom":
        return RISK_PRESETS[preset]
    return (
        float(params.get("slMult") or 1.5),
        float(params.get("tp1Mult") or 1.0),
        float(params.get("tp2Mult") or 2.0),
        float(params.get("tp3Mult") or 3.0),
    )


def _normalize_ohlc(candles: list[dict[str, Any]]) -> tuple[list[float], list[float], list[float], list[float], list[float]]:
    opens, highs, lows, closes, vols = [], [], [], [], []
    for c in candles:
        close = float(c["close"])
        open_ = float(c.get("open", close))
        high = float(c.get("high", max(open_, close)))
        low = float(c.get("low", min(open_, close)))
        vol = float(c.get("volume", 0.0) or 0.0)
        opens.append(open_)
        highs.append(high)
        lows.append(low)
        closes.append(close)
        vols.append(vol)
    return opens, highs, lows, closes, vols


def analyze_ltm(candles: list[dict[str, Any]], params: dict[str, Any] | None = None) -> dict[str, Any]:
    """Run LTM trail + scored retest engine; return signals and paper metrics."""
    params = dict(params or {})
    opens, highs, lows, closes, vols = _normalize_ohlc(candles)
    n = len(closes)
    if n < 40:
        return {
            "success": False,
            "error": f"LTM needs ≥40 bars; got {n}",
            "signals": [],
            "trades": 0,
        }

    atr_len = max(5, int(params.get("atrLen") or params.get("ATR Length") or 13))
    atr_risk_len = max(5, int(params.get("atrLenRisk") or params.get("ATR Length (Risk)") or 14))
    min_score = int(params.get("minScore") or params.get("Min Retest Score (0-100)") or 80)
    retest_window = int(params.get("retestWindow") or params.get("Retest Window (bars)") or 8)
    cooldown = int(params.get("cooldown") or params.get("Signal Cooldown (bars)") or 5)
    flip_str = str(params.get("flipBand") or params.get("Flip Band") or "Balanced (Band 3)")
    flip_choice = FLIP_BAND.get(flip_str, 3)
    sl_mode = str(params.get("slMode") or params.get("SL Mode") or "Wick-Anchored")
    be_after_tp1 = bool(params.get("beAfterTp1", params.get("Break-Even After TP1", True)))
    if isinstance(be_after_tp1, str):
        be_after_tp1 = be_after_tp1.lower() in {"true", "1", "yes"}

    base, step = _resolve_band(params)
    m1, m2, m3, m4 = base, base * (1 + step), base * (1 + 2 * step), base * (1 + 3 * step)
    sl_mult, tp1m, tp2m, tp3m = _resolve_risk(params)

    atr = _atr(highs, lows, closes, atr_len)
    atr_risk = _atr(highs, lows, closes, atr_risk_len)
    ema50 = _ema(closes, 50)
    vol_sma = _sma(vols, 20)
    has_vol = sum(vols) > 0

    warmup = max(atr_len * 3, 60)
    trend = 1
    ts = [math.nan, math.nan, math.nan, math.nan]
    trend_start = 0
    pending_long = pending_short = 0
    pending_long_depth = pending_short_depth = 0
    last_sig_bar = -10_000

    signals: list[dict[str, Any]] = []

    # Paper trade state
    active_dir = 0
    entry = sl = tp1 = tp2 = tp3 = math.nan
    entry_bar = -1
    tp1_hit = tp2_hit = tp3_hit = be_active = False
    wins = losses = 0
    equity = 1_000.0
    peak = equity
    max_dd = 0.0
    trade_pnls: list[float] = []

    def close_trade(win: bool, pnl_pct: float) -> None:
        nonlocal wins, losses, equity, peak, max_dd, active_dir
        nonlocal entry, sl, tp1, tp2, tp3, entry_bar, tp1_hit, tp2_hit, tp3_hit, be_active
        if win:
            wins += 1
        else:
            losses += 1
        pnl = equity * (pnl_pct / 100.0)
        equity += pnl
        trade_pnls.append(pnl)
        peak = max(peak, equity)
        if peak > 0:
            max_dd = max(max_dd, (peak - equity) / peak)
        active_dir = 0
        entry = sl = tp1 = tp2 = tp3 = math.nan
        entry_bar = -1
        tp1_hit = tp2_hit = tp3_hit = be_active = False

    for i in range(n):
        src = closes[i]
        a = atr[i] if atr[i] > 0 else abs(highs[i] - lows[i]) or 1e-9
        upper = [src - a * m1, src - a * m2, src - a * m3, src - a * m4]
        lower = [src + a * m1, src + a * m2, src + a * m3, src + a * m4]

        prev_ts = list(ts)
        flip_prev = prev_ts[flip_choice - 1] if not math.isnan(prev_ts[flip_choice - 1]) else math.nan
        do_flip_down = trend == 1 and not math.isnan(flip_prev) and src < flip_prev
        do_flip_up = trend == -1 and not math.isnan(flip_prev) and src > flip_prev
        flip_bar = False

        if trend == 1:
            if do_flip_down:
                trend = -1
                ts = lower[:]
                flip_bar = True
            else:
                ts = [
                    max(upper[0], prev_ts[0]) if not math.isnan(prev_ts[0]) else upper[0],
                    max(upper[1], prev_ts[1]) if not math.isnan(prev_ts[1]) else upper[1],
                    max(upper[2], prev_ts[2]) if not math.isnan(prev_ts[2]) else upper[2],
                    max(upper[3], prev_ts[3]) if not math.isnan(prev_ts[3]) else upper[3],
                ]
        else:
            if do_flip_up:
                trend = 1
                ts = upper[:]
                flip_bar = True
            else:
                ts = [
                    min(lower[0], prev_ts[0]) if not math.isnan(prev_ts[0]) else lower[0],
                    min(lower[1], prev_ts[1]) if not math.isnan(prev_ts[1]) else lower[1],
                    min(lower[2], prev_ts[2]) if not math.isnan(prev_ts[2]) else lower[2],
                    min(lower[3], prev_ts[3]) if not math.isnan(prev_ts[3]) else lower[3],
                ]

        if flip_bar:
            trend_start = i
            pending_long = pending_short = 0
            pending_long_depth = pending_short_depth = 0

        bars_in_trend = i - trend_start
        warmed = i >= warmup

        # Manage open trade
        if active_dir != 0 and i > entry_bar:
            hi, lo = highs[i], lows[i]
            sl_hit = lo <= sl if active_dir == 1 else hi >= sl
            t1 = hi >= tp1 if active_dir == 1 else lo <= tp1
            t2 = hi >= tp2 if active_dir == 1 else lo <= tp2
            t3 = hi >= tp3 if active_dir == 1 else lo <= tp3
            if t1 and not tp1_hit and not sl_hit:
                tp1_hit = True
                if be_after_tp1 and not be_active:
                    sl = entry
                    be_active = True
            if t2 and not tp2_hit and not sl_hit:
                tp2_hit = True
            if sl_hit or t3:
                if active_dir == 1:
                    exit_px = sl if sl_hit else tp3
                else:
                    exit_px = sl if sl_hit else tp3
                pnl_pct = ((exit_px - entry) / entry) * 100.0 * active_dir
                close_trade(win=tp1_hit, pnl_pct=pnl_pct)
                if t3 and not sl_hit:
                    tp3_hit = True

        pending_long = max(pending_long - 1, 0)
        pending_short = max(pending_short - 1, 0)
        if pending_long == 0:
            pending_long_depth = 0
        if pending_short == 0:
            pending_short_depth = 0

        if not warmed or math.isnan(ts[0]):
            continue

        # Touch depth
        touch_l = 0
        touch_s = 0
        if trend == 1:
            if lows[i] <= ts[3]:
                touch_l = 4
            elif lows[i] <= ts[2]:
                touch_l = 3
            elif lows[i] <= ts[1]:
                touch_l = 2
            elif lows[i] <= ts[0]:
                touch_l = 1
        else:
            if highs[i] >= ts[3]:
                touch_s = 4
            elif highs[i] >= ts[2]:
                touch_s = 3
            elif highs[i] >= ts[1]:
                touch_s = 2
            elif highs[i] >= ts[0]:
                touch_s = 1

        if touch_l:
            pending_long = retest_window
            pending_long_depth = max(pending_long_depth, touch_l)
        if touch_s:
            pending_short = retest_window
            pending_short_depth = max(pending_short_depth, touch_s)

        long_reclaim = (
            pending_long > 0 and trend == 1 and closes[i] > ts[0] and closes[i] > opens[i]
        )
        short_reclaim = (
            pending_short > 0 and trend == -1 and closes[i] < ts[0] and closes[i] < opens[i]
        )

        rng = highs[i] - lows[i]
        clr_l = (closes[i] - lows[i]) / rng if rng > 0 else 0.5
        clr_s = (highs[i] - closes[i]) / rng if rng > 0 else 0.5
        depth_pts_l = {2: 25, 3: 18, 1: 15, 4: 10}.get(pending_long_depth, 0)
        depth_pts_s = {2: 25, 3: 18, 1: 15, 4: 10}.get(pending_short_depth, 0)
        candle_l = 20 if clr_l > 0.7 else 12 if clr_l > 0.5 else 5
        candle_s = 20 if clr_s > 0.7 else 12 if clr_s > 0.5 else 5
        age_pts = 15 if 10 <= bars_in_trend <= 150 else 8 if bars_in_trend < 10 else 5
        vol_base = vol_sma[i - 1] if i > 0 else vol_sma[i]
        if has_vol:
            vol_pts = 20 if vols[i] > vol_base * 1.2 else 12 if vols[i] > vol_base else 5
        else:
            vol_pts = 12
        bias = 1 if closes[i] > ema50[i] else -1
        bias_l = 20 if bias == 1 else 10 if bias == 0 else 0
        bias_s = 20 if bias == -1 else 10 if bias == 0 else 0
        long_score = depth_pts_l + candle_l + age_pts + vol_pts + bias_l
        short_score = depth_pts_s + candle_s + age_pts + vol_pts + bias_s

        cooldown_ok = i - last_sig_bar >= cooldown
        conf_long = long_reclaim and cooldown_ok and long_score >= min_score
        conf_short = short_reclaim and cooldown_ok and short_score >= min_score
        conf_bull_flip = flip_bar and trend == 1
        conf_bear_flip = flip_bar and trend == -1

        long_entry = conf_long or conf_bull_flip
        short_entry = conf_short or conf_bear_flip

        if conf_long or conf_bull_flip:
            signals.append(
                {
                    "bar": i,
                    "type": "long_retest" if conf_long else "bull_flip",
                    "score": long_score if conf_long else 0,
                    "price": closes[i],
                    "trend": trend,
                }
            )
            if conf_long:
                last_sig_bar = i
                pending_long = pending_long_depth = 0
        if conf_short or conf_bear_flip:
            signals.append(
                {
                    "bar": i,
                    "type": "short_retest" if conf_short else "bear_flip",
                    "score": short_score if conf_short else 0,
                    "price": closes[i],
                    "trend": trend,
                }
            )
            if conf_short:
                last_sig_bar = i
                pending_short = pending_short_depth = 0

        # Reversal / entries
        risk_a = atr_risk[i] if atr_risk[i] > 0 else a
        if active_dir == 1 and short_entry:
            pnl_pct = ((closes[i] - entry) / entry) * 100.0
            close_trade(win=tp1_hit, pnl_pct=pnl_pct)
        elif active_dir == -1 and long_entry:
            pnl_pct = ((entry - closes[i]) / entry) * 100.0
            close_trade(win=tp1_hit, pnl_pct=pnl_pct)

        if long_entry and active_dir == 0 and risk_a > 0:
            if sl_mode == "ATR":
                sl_px = closes[i] - risk_a * sl_mult
            else:
                sl_px = min(lows[i] - risk_a * 0.25, closes[i] - risk_a * 0.5)
            risk = closes[i] - sl_px
            if risk > 0:
                entry, sl = closes[i], sl_px
                tp1, tp2, tp3 = entry + risk * tp1m, entry + risk * tp2m, entry + risk * tp3m
                active_dir, entry_bar = 1, i
                tp1_hit = tp2_hit = tp3_hit = be_active = False
        elif short_entry and active_dir == 0 and risk_a > 0:
            if sl_mode == "ATR":
                sl_px = closes[i] + risk_a * sl_mult
            else:
                sl_px = max(highs[i] + risk_a * 0.25, closes[i] + risk_a * 0.5)
            risk = sl_px - closes[i]
            if risk > 0:
                entry, sl = closes[i], sl_px
                tp1, tp2, tp3 = entry - risk * tp1m, entry - risk * tp2m, entry - risk * tp3m
                active_dir, entry_bar = -1, i
                tp1_hit = tp2_hit = tp3_hit = be_active = False

    trades = wins + losses
    win_rate = (wins / trades * 100.0) if trades else 0.0
    gross_win = sum(p for p in trade_pnls if p > 0)
    gross_loss = abs(sum(p for p in trade_pnls if p <= 0))
    pf = (gross_win / gross_loss) if gross_loss > 1e-9 else (gross_win if gross_win > 0 else 0.0)
    retests = [s for s in signals if "retest" in s["type"]]
    avg_score = sum(s["score"] for s in retests) / len(retests) if retests else 0.0

    return {
        "success": True,
        "engine": "ltm_v1.3",
        "netProfit": round(equity - 1_000.0, 4),
        "profitFactor": round(float(pf), 3),
        "winRate": round(win_rate, 2),
        "trades": trades,
        "wins": wins,
        "losses": losses,
        "maxDrawdown": round(max_dd, 6),
        "signalCount": len(signals),
        "retestCount": len(retests),
        "avgRetestScore": round(avg_score, 2),
        "signals": signals[-40:],
        "paramsUsed": {
            "bandBase": base,
            "bandStep": step,
            "flipBand": flip_choice,
            "minScore": min_score,
            "slMult": sl_mult,
            "tp": [tp1m, tp2m, tp3m],
            "slMode": sl_mode,
        },
        "fitness": (equity - 1_000.0) - max_dd * 700.0 + (win_rate / 100.0) * 50.0 + avg_score * 0.3,
    }


def optimize_ltm(
    candles: list[dict[str, Any]],
    base_params: dict[str, Any] | None = None,
    *,
    min_trades: int = 1,
    limit: int = 48,
) -> dict[str, Any]:
    """Small grid over LTM presets / minScore / flip band."""
    base_params = dict(base_params or {})
    grid = []
    for band in ("Scalping", "Balanced", "Deep Trend"):
        for flip in ("Fast (Band 2)", "Balanced (Band 3)", "Deep (Band 4)"):
            for score in (55, 70, 80):
                for risk in ("Scalping", "Balanced", "Conservative"):
                    grid.append(
                        {
                            **base_params,
                            "bandPreset": band,
                            "flipBand": flip,
                            "minScore": score,
                            "riskPreset": risk,
                        }
                    )
    results = []
    best = None
    tested = 0
    for params in grid:
        tested += 1
        metrics = analyze_ltm(candles, params)
        if not metrics.get("success"):
            continue
        row = {"params": params, "result": metrics, "isDisqualified": metrics["trades"] < min_trades}
        results.append(row)
        if not row["isDisqualified"]:
            if best is None or metrics["fitness"] > best["result"]["fitness"]:
                best = row
        if tested >= limit:
            break
    if best is None and results:
        best = max(results, key=lambda r: r["result"].get("fitness", -1e9))
    return {"tested": tested, "best": best, "results": results}


def is_ltm_strategy(payload: dict[str, Any]) -> bool:
    strategy = str(payload.get("strategy") or "").lower()
    name = str(payload.get("pineName") or "").lower()
    source = str(payload.get("pineSource") or "")
    script_id = str(payload.get("scriptId") or "").lower()
    if strategy in {"ltm", "ltm_willy", "liquidity_trail", "ltm_willy_v130"}:
        return True
    if "ltm" in script_id or "liquidity_trail" in script_id:
        return True
    if "liquidity trail matrix" in name or "ltm [" in name or "willyalgo" in name:
        return True
    if "Liquidity Trail Matrix" in source or "LTM [WillyAlgoTrader]" in source:
        return True
    return False


def run_ltm_optimize(
    payload: dict[str, Any],
    candles: list[dict[str, Any]],
    *,
    candle_source: str = "ohlcv",
) -> dict[str, Any]:
    """UI-compatible optimize response using LTM analyzer grid."""
    symbol = str(payload.get("symbol") or "BTCUSD").upper()
    timeframe = str(payload.get("timeframe") or "5m")
    min_trades = max(1, int(payload.get("minTrades") or 5))
    primary = str(payload.get("primaryObjective") or "profit_factor")
    secondary = str(payload.get("secondaryObjective") or "percent_profitable")
    params = dict(payload.get("parameters") or {})

    if len(candles) < 40:
        return {
            "success": False,
            "error": f"LTM needs at least 40 candles; got {len(candles)}",
            "source": "ltm-analyzer",
        }

    opt = optimize_ltm(candles, params, min_trades=min_trades, limit=48)
    best = opt.get("best")
    if not best:
        return {"success": False, "error": "LTM grid produced no results", "source": "ltm-analyzer"}

    def score_row(row: dict[str, Any]) -> tuple[float, float]:
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

    ranked = sorted(opt["results"], key=score_row, reverse=True)
    winner_row = best if not best["isDisqualified"] else max(ranked, key=score_row)
    wm = winner_row["result"]
    wp = winner_row["params"]
    label = (
        f"LTM-{wp.get('bandPreset', '?')[:3]}-"
        f"F{FLIP_BAND.get(str(wp.get('flipBand')), 3)}-"
        f"S{wp.get('minScore')}"
    )
    winner = {
        "label": label,
        "profitFactor": wm["profitFactor"],
        "netProfit": wm["netProfit"],
        "winRate": wm["winRate"],
        "trades": wm["trades"],
        "inputs": wp,
        "maxDrawdown": wm["maxDrawdown"],
        "avgRetestScore": wm.get("avgRetestScore"),
    }
    results = []
    for idx, row in enumerate(ranked[:40], start=1):
        m = row["result"]
        p = row["params"]
        lab = f"LTM-{str(p.get('bandPreset', '?'))[:3]}-S{p.get('minScore')}"
        results.append(
            {
                "rank": idx,
                "label": lab,
                "profitFactor": m["profitFactor"],
                "winRate": m["winRate"],
                "netProfit": m["netProfit"],
                "trades": m["trades"],
                "maxDrawdown": m["maxDrawdown"],
                "inputs": p,
                "isWinner": lab == label or row is winner_row,
                "isDisqualified": row["isDisqualified"],
            }
        )

    source = f"ltm-analyzer/{candle_source}"
    bericht = (
        f"### LTM Liquidity Trail Matrix analyzer (v1.3 port)\n"
        f"- Symbol: `{symbol}` TF `{timeframe}` · candles `{len(candles)}` · source `{source}`\n"
        f"- Engine: ATR trail bands + scored retests (depth/candle/vol/bias/age) + wick/ATR risk\n"
        f"- Grid tested: `{opt['tested']}` · Winner **{label}** "
        f"PF={winner['profitFactor']} WR={winner['winRate']}% "
        f"NP={winner['netProfit']} avgScore={wm.get('avgRetestScore')}\n"
        f"- Signals: {wm.get('signalCount')} (retests {wm.get('retestCount')})\n"
        f"- Pine visuals/profile stay on TradingView; this path is the precision signal sim.\n"
    )
    return {
        "success": True,
        "winner": winner,
        "bericht": bericht,
        "selfTest": "PASS: LTM analyzer grid completed; vision/YouTube not used.",
        "results": results,
        "source": source,
        "candlesUsed": len(candles),
        "tested": opt["tested"],
        "ltm": {
            "avgRetestScore": wm.get("avgRetestScore"),
            "signalCount": wm.get("signalCount"),
            "paramsUsed": wm.get("paramsUsed"),
            "signals": wm.get("signals"),
        },
    }
