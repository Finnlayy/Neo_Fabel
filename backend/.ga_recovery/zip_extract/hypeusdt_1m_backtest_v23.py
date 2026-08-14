#!/usr/bin/env python3
"""Backtest v2.3.1-style logic on HYPEUSDT 1m candles from Bybit."""

from __future__ import annotations

import argparse
import json
import math
import time
from collections.abc import Sequence
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import requests

WORKDIR = Path(__file__).resolve().parent
CACHE_DIR = WORKDIR / "data_cache"
RESULTS_DIR = WORKDIR / "optimizer_results"
BYBIT_BASE_URL = "https://api.bybit.com"

SYMBOL = "HYPEUSDT"
INTERVAL = 1
DEFAULT_BARS = 20_000


@dataclass(frozen=True)
class Candle:
    ts: int
    o: float
    h: float
    l: float
    c: float
    v: float


@dataclass
class Params:
    tf_h4: int = 48
    tf_h1: int = 12
    tf_m15: int = 3
    tf_m5: int = 1
    en_h4: bool = True
    en_h1: bool = True
    en_m15: bool = True
    en_m5: bool = False
    min_alignment: int = 3
    ob_atr_mul: float = 1.6
    ob_pivot: int = 6
    max_ob_boxes: int = 25
    max_fvg_boxes: int = 25
    sl_atr_mul: float = 1.4
    tp_atr_mul: float = 2.8
    risk_per_trade: float = 1.0
    use_trail: bool = False
    trail_atr: float = 1.2
    use_max_dd: bool = True
    max_dd_pct: float = 8.0
    use_max_bars: bool = False
    max_bars_held: int = 48
    qty_step: float = 0.001
    min_conf: int = 11
    use_vol: bool = True
    vol_mult: float = 1.05
    vol_period: int = 20
    use_time: bool = True
    start_time: int = 1530
    end_time: int = 2200
    session_timezone: str = "America/New_York"
    warmup_bars: int = 50
    use_daily: bool = True
    daily_lim: float = 3.0
    use_ema_filter: bool = True
    ema_len: int = 200
    use_rsi_filter: bool = True
    rsi_len: int = 14
    rsi_ob: float = 78.0
    rsi_os: float = 22.0
    use_atr_filter: bool = True
    atr_min_pct: float = 0.15
    allow_short: bool = False
    w_align_full: int = 4
    w_align_part: int = 2
    w_cisd: int = 3
    w_ob_touch: int = 3
    w_fvg_touch: int = 3
    w_vol_score: int = 2
    w_body_score: int = 2
    body_atr_mul: float = 0.5


@dataclass
class Trade:
    side: str
    entry_ts: int
    exit_ts: int
    entry_price: float
    exit_price: float
    qty: float
    pnl: float


def bybit_get(path: str, params: dict[str, object]) -> dict:
    r = requests.get(f"{BYBIT_BASE_URL}{path}", params=params, timeout=30)
    r.raise_for_status()
    payload = r.json()
    if payload.get("retCode") != 0:
        raise RuntimeError(f"Bybit error: {payload}")
    return payload["result"]


def fetch_1m_klines(symbol: str, bars_target: int) -> list[Candle]:
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    cache_path = CACHE_DIR / f"{symbol}_1m_{bars_target}.json"
    if cache_path.exists():
        rows = json.loads(cache_path.read_text(encoding="utf-8"))
        return [Candle(**row) for row in rows]

    bars: list[Candle] = []
    end_ms = int(time.time() * 1000)
    tf_ms = 60_000
    while len(bars) < bars_target:
        remaining = bars_target - len(bars)
        limit = min(remaining, 1000)
        result = bybit_get(
            "/v5/market/kline",
            {
                "category": "linear",
                "symbol": symbol,
                "interval": str(INTERVAL),
                "end": end_ms,
                "limit": limit,
            },
        )["list"]
        if not result:
            break
        chunk = [
            Candle(
                ts=int(row[0]),
                o=float(row[1]),
                h=float(row[2]),
                l=float(row[3]),
                c=float(row[4]),
                v=float(row[5]),
            )
            for row in result
        ]
        chunk.sort(key=lambda c: c.ts)
        oldest = chunk[0].ts
        bars = chunk + bars
        end_ms = oldest - tf_ms
        time.sleep(0.08)
        if len(chunk) < limit:
            break

    deduped = {c.ts: c for c in bars}
    ordered = [deduped[k] for k in sorted(deduped)]
    cache_path.write_text(
        json.dumps([asdict(c) for c in ordered], ensure_ascii=True, indent=2),
        encoding="utf-8",
    )
    return ordered


def ema(values: Sequence[float], period: int) -> list[float]:
    if not values:
        return []
    alpha = 2.0 / (period + 1.0)
    out = [values[0]]
    for x in values[1:]:
        out.append(out[-1] * (1.0 - alpha) + x * alpha)
    return out


def sma(values: Sequence[float], period: int) -> list[float]:
    out: list[float] = []
    s = 0.0
    for i, x in enumerate(values):
        s += x
        if i >= period:
            s -= values[i - period]
        out.append(s / min(i + 1, period))
    return out


def atr(candles: Sequence[Candle], period: int = 14) -> list[float]:
    trs: list[float] = []
    prev = candles[0].c
    for c in candles:
        trs.append(max(c.h - c.l, abs(c.h - prev), abs(c.l - prev)))
        prev = c.c
    return ema(trs, period)


def rsi(closes: Sequence[float], length: int) -> list[float]:
    if len(closes) < 2:
        return [50.0] * len(closes)
    gains = [0.0]
    losses = [0.0]
    for i in range(1, len(closes)):
        ch = closes[i] - closes[i - 1]
        gains.append(max(ch, 0.0))
        losses.append(max(-ch, 0.0))

    out = [50.0] * len(closes)
    avg_gain = sum(gains[1 : length + 1]) / length if len(closes) > length else sum(gains[1:]) / max(1, len(closes) - 1)
    avg_loss = sum(losses[1 : length + 1]) / length if len(closes) > length else sum(losses[1:]) / max(1, len(closes) - 1)

    start = max(1, length)
    for i in range(start, len(closes)):
        if i > start:
            avg_gain = (avg_gain * (length - 1) + gains[i]) / length
            avg_loss = (avg_loss * (length - 1) + losses[i]) / length
        if avg_loss == 0:
            out[i] = 100.0
        else:
            rs = avg_gain / avg_loss
            out[i] = 100.0 - (100.0 / (1.0 + rs))
    return out


def norm_hhmm(hhmm: int) -> int:
    h = math.floor(hhmm / 100.0)
    m = hhmm % 100
    h = max(0, min(23, h))
    m = max(0, min(59, m))
    return h * 100 + m


def in_session(ts_ms: int, start_hhmm: int, end_hhmm: int, tz: str) -> bool:
    if tz == "Exchange":
        tz = "UTC"
    try:
        tzinfo = ZoneInfo(tz)
    except ZoneInfoNotFoundError:
        tzinfo = UTC
    dt = datetime.fromtimestamp(ts_ms / 1000.0, tz=tzinfo)
    now_hhmm = dt.hour * 100 + dt.minute
    regular = start_hhmm <= end_hhmm
    return (start_hhmm <= now_hhmm <= end_hhmm) if regular else (now_hhmm >= start_hhmm or now_hhmm <= end_hhmm)


def round_qty(qty: float, step: float) -> float:
    return math.floor(qty / step) * step


def cisd_sequence(candles: Sequence[Candle]) -> tuple[list[int], list[bool], list[bool]]:
    state = 0
    states: list[int] = []
    bull: list[bool] = []
    bear: list[bool] = []
    for i, c in enumerate(candles):
        prev = candles[i - 1] if i > 0 else c
        is_bull = c.c > c.o
        is_bear = c.c < c.o
        bull_tr = False
        bear_tr = False
        inside = c.h < prev.h and c.l > prev.l
        if is_bear and state != -1 and c.c < prev.o and not inside:
            state = -1
            bear_tr = True
        if is_bull and state != 1 and c.c > prev.o and not inside:
            state = 1
            bull_tr = True
        states.append(state)
        bull.append(bull_tr)
        bear.append(bear_tr)
    return states, bull, bear


def aggregate(candles: Sequence[Candle], tf_minutes: int) -> list[Candle]:
    bucket_ms = tf_minutes * 60_000
    grouped: list[Candle] = []
    current: int | None = None
    rows: list[Candle] = []
    for c in candles:
        bucket = (c.ts // bucket_ms) * bucket_ms
        if current is None:
            current = bucket
        if bucket != current:
            if rows:
                grouped.append(
                    Candle(
                        ts=current,
                        o=rows[0].o,
                        h=max(x.h for x in rows),
                        l=min(x.l for x in rows),
                        c=rows[-1].c,
                        v=sum(x.v for x in rows),
                    )
                )
            current = bucket
            rows = []
        rows.append(c)
    if rows:
        grouped.append(
            Candle(
                ts=current if current is not None else rows[0].ts,
                o=rows[0].o,
                h=max(x.h for x in rows),
                l=min(x.l for x in rows),
                c=rows[-1].c,
                v=sum(x.v for x in rows),
            )
        )
    return grouped


def mtf_state_for_1m(candles_1m: Sequence[Candle], tf_minutes: int) -> dict[int, int]:
    agg = aggregate(candles_1m, tf_minutes)
    states, _, _ = cisd_sequence(agg)
    by_bucket = {c.ts: s for c, s in zip(agg, states)}
    tf_ms = tf_minutes * 60_000
    out: dict[int, int] = {}
    for c in candles_1m:
        bucket = (c.ts // tf_ms) * tf_ms
        prev_bucket = bucket - tf_ms
        out[c.ts] = by_bucket.get(prev_bucket, 0)
    return out


def backtest(candles: Sequence[Candle], p: Params) -> dict:
    closes = [c.c for c in candles]
    opens = [c.o for c in candles]
    highs = [c.h for c in candles]
    lows = [c.l for c in candles]
    vols = [c.v for c in candles]

    atr14 = atr(candles, 14)
    ema200 = ema(closes, p.ema_len)
    rsi14 = rsi(closes, p.rsi_len)
    vol_sma = sma(vols, p.vol_period)

    _local_state, local_bull_cisd, local_bear_cisd = cisd_sequence(candles)
    state_h4 = mtf_state_for_1m(candles, p.tf_h4)
    state_h1 = mtf_state_for_1m(candles, p.tf_h1)
    state_m15 = mtf_state_for_1m(candles, p.tf_m15)
    state_m5 = mtf_state_for_1m(candles, p.tf_m5)

    start_hhmm = norm_hhmm(p.start_time)
    end_hhmm = norm_hhmm(p.end_time)

    bull_ob: list[tuple[float, float]] = []
    bear_ob: list[tuple[float, float]] = []
    bull_fvg: list[tuple[float, float]] = []
    bear_fvg: list[tuple[float, float]] = []

    equity_cash = 100.0
    equity_peak = closes[0]
    current_dd_pct = 0.0
    daily_start_price = closes[0]
    daily_pnl_pct = 0.0
    prev_day = datetime.fromtimestamp(candles[0].ts / 1000.0, tz=UTC).date()

    pos_side = 0
    pos_qty = 0.0
    entry_price = math.nan
    sl_price = math.nan
    tp_price = math.nan
    trail_price = math.nan
    bars_in_pos = 0

    pending_entry: tuple[int, float] | None = None
    pending_force_close = False

    trades: list[Trade] = []
    last_entry_ts = candles[0].ts

    equity_curve: list[float] = []

    for i, c in enumerate(candles):
        # process pending close at next bar open
        if pending_force_close and pos_side != 0:
            exit_px = c.o
            pnl = (exit_px - entry_price) * pos_qty if pos_side == 1 else (entry_price - exit_px) * pos_qty
            equity_cash += pnl
            trades.append(
                Trade(
                    side="long" if pos_side == 1 else "short",
                    entry_ts=last_entry_ts,
                    exit_ts=c.ts,
                    entry_price=entry_price,
                    exit_price=exit_px,
                    qty=pos_qty,
                    pnl=pnl,
                )
            )
            pos_side = 0
            pos_qty = 0.0
            entry_price = math.nan
            sl_price = math.nan
            tp_price = math.nan
            trail_price = math.nan
            bars_in_pos = 0
        pending_force_close = False

        # process pending entry at next bar open
        if pending_entry is not None and pos_side == 0:
            side, qty = pending_entry
            if qty > 0:
                pos_side = side
                pos_qty = qty
                entry_price = c.o
                last_entry_ts = c.ts
                sl_price = entry_price - atr14[i] * p.sl_atr_mul if side == 1 else entry_price + atr14[i] * p.sl_atr_mul
                tp_price = entry_price + atr14[i] * p.tp_atr_mul if side == 1 else entry_price - atr14[i] * p.tp_atr_mul
                trail_price = sl_price if p.use_trail else math.nan
                bars_in_pos = 0
        pending_entry = None

        # bar-based bookkeeping
        if pos_side != 0:
            bars_in_pos += 1

        # daily reset
        current_day = datetime.fromtimestamp(c.ts / 1000.0, tz=UTC).date()
        if current_day != prev_day:
            daily_start_price = c.c
            daily_pnl_pct = 0.0
            equity_peak = c.c
            current_dd_pct = 0.0
            prev_day = current_day

        daily_pnl_pct = ((c.c - daily_start_price) / daily_start_price) * 100.0 if daily_start_price > 0 else 0.0
        equity_peak = max(equity_peak, c.c)
        current_dd_pct = ((equity_peak - c.c) / equity_peak) * 100.0 if equity_peak > 0 else 0.0

        # OB/FVG creation
        if i >= p.ob_pivot * 2:
            piv = i - p.ob_pivot
            left = piv - p.ob_pivot
            right = piv + p.ob_pivot
            if left >= 0 and right <= i:
                if lows[piv] == min(lows[left : right + 1]):
                    ob_top = highs[piv]
                    ob_bot = lows[piv]
                    if (ob_top - ob_bot) <= atr14[i] * p.ob_atr_mul:
                        bull_ob.append((ob_top, ob_bot))
                        if len(bull_ob) > p.max_ob_boxes:
                            bull_ob.pop(0)
                if highs[piv] == max(highs[left : right + 1]):
                    ob_top = highs[piv]
                    ob_bot = lows[piv]
                    if (ob_top - ob_bot) <= atr14[i] * p.ob_atr_mul:
                        bear_ob.append((ob_top, ob_bot))
                        if len(bear_ob) > p.max_ob_boxes:
                            bear_ob.pop(0)

        if i >= 2:
            bull_fvg_now = lows[i] > highs[i - 2] and closes[i - 1] > opens[i - 1]
            bear_fvg_now = highs[i] < lows[i - 2] and closes[i - 1] < opens[i - 1]
            if bull_fvg_now:
                bull_fvg.append((lows[i], highs[i - 2]))
                if len(bull_fvg) > p.max_fvg_boxes:
                    bull_fvg.pop(0)
            if bear_fvg_now:
                bear_fvg.append((lows[i - 2], highs[i]))
                if len(bear_fvg) > p.max_fvg_boxes:
                    bear_fvg.pop(0)

        # touches
        bull_ob_touch = any((c.l <= top and c.h >= bot) for top, bot in bull_ob[-5:])
        bear_ob_touch = any((c.h >= bot and c.l <= top) for top, bot in bear_ob[-5:])
        bull_fvg_touch = any((c.l <= top and c.h >= bot) for top, bot in bull_fvg[-5:])
        bear_fvg_touch = any((c.h >= bot and c.l <= top) for top, bot in bear_fvg[-5:])

        # alignment
        sh4 = state_h4[c.ts] if p.en_h4 else 0
        sh1 = state_h1[c.ts] if p.en_h1 else 0
        sm15 = state_m15[c.ts] if p.en_m15 else 0
        sm5 = state_m5[c.ts] if p.en_m5 else 0
        bull_count = (1 if p.en_h4 and sh4 == 1 else 0) + (1 if p.en_h1 and sh1 == 1 else 0) + (1 if p.en_m15 and sm15 == 1 else 0) + (1 if p.en_m5 and sm5 == 1 else 0)
        bear_count = (1 if p.en_h4 and sh4 == -1 else 0) + (1 if p.en_h1 and sh1 == -1 else 0) + (1 if p.en_m15 and sm15 == -1 else 0) + (1 if p.en_m5 and sm5 == -1 else 0)
        active_tfs = (1 if p.en_h4 else 0) + (1 if p.en_h1 else 0) + (1 if p.en_m15 else 0) + (1 if p.en_m5 else 0)
        bull_aligned = bull_count >= p.min_alignment
        bear_aligned = bear_count >= p.min_alignment

        # scoring
        bull_conf = 0
        bull_conf += p.w_align_full if (bull_count == active_tfs and active_tfs >= 3) else (p.w_align_part if bull_count >= p.min_alignment else 0)
        bull_conf += p.w_cisd if local_bull_cisd[i] else 0
        bull_conf += p.w_ob_touch if bull_ob_touch else 0
        bull_conf += p.w_fvg_touch if bull_fvg_touch else 0
        bull_conf += p.w_vol_score if ((p.use_vol and c.v > vol_sma[i] * p.vol_mult) or (not p.use_vol)) else 0
        bull_conf += p.w_body_score if (c.c > c.o and (c.c - c.o) > atr14[i] * p.body_atr_mul) else 0

        bear_conf = 0
        bear_conf += p.w_align_full if (bear_count == active_tfs and active_tfs >= 3) else (p.w_align_part if bear_count >= p.min_alignment else 0)
        bear_conf += p.w_cisd if local_bear_cisd[i] else 0
        bear_conf += p.w_ob_touch if bear_ob_touch else 0
        bear_conf += p.w_fvg_touch if bear_fvg_touch else 0
        bear_conf += p.w_vol_score if ((p.use_vol and c.v > vol_sma[i] * p.vol_mult) or (not p.use_vol)) else 0
        bear_conf += p.w_body_score if (c.o > c.c and (c.o - c.c) > atr14[i] * p.body_atr_mul) else 0

        # filters
        time_ok = in_session(c.ts, start_hhmm, end_hhmm, p.session_timezone) if p.use_time else True
        ema_long_ok = (c.c > ema200[i]) if p.use_ema_filter else True
        ema_short_ok = (c.c < ema200[i]) if p.use_ema_filter else True
        rsi_long_ok = (rsi14[i] < p.rsi_ob) if p.use_rsi_filter else True
        rsi_short_ok = (rsi14[i] > p.rsi_os) if p.use_rsi_filter else True
        atr_pct = (atr14[i] / c.c) * 100.0 if c.c > 0 else 0.0
        atr_ok = (atr_pct >= p.atr_min_pct) if p.use_atr_filter else True
        vol_ok = (c.v > vol_sma[i] * p.vol_mult) if p.use_vol else True
        daily_limit_ok = (daily_pnl_pct > -p.daily_lim) if p.use_daily else True
        dd_ok = (current_dd_pct < p.max_dd_pct) if p.use_max_dd else True
        ready = i >= p.warmup_bars

        all_filters_long = time_ok and ema_long_ok and rsi_long_ok and atr_ok and vol_ok and daily_limit_ok and dd_ok
        all_filters_short = time_ok and ema_short_ok and rsi_short_ok and atr_ok and vol_ok and daily_limit_ok and dd_ok
        long_setup = bull_aligned and local_bull_cisd[i] and bull_conf >= p.min_conf and all_filters_long
        short_setup = p.allow_short and bear_aligned and local_bear_cisd[i] and bear_conf >= p.min_conf and all_filters_short

        # trailing update
        if p.use_trail and pos_side == 1 and not math.isnan(trail_price):
            new_trail = c.h - atr14[i] * p.trail_atr
            trail_price = max(trail_price, new_trail)
        if p.use_trail and pos_side == -1 and not math.isnan(trail_price):
            new_trail = c.l + atr14[i] * p.trail_atr
            trail_price = min(trail_price, new_trail)

        active_long_stop = max(sl_price, trail_price) if (pos_side == 1 and p.use_trail and not math.isnan(trail_price)) else (sl_price if pos_side == 1 else math.nan)
        active_short_stop = min(sl_price, trail_price) if (pos_side == -1 and p.use_trail and not math.isnan(trail_price)) else (sl_price if pos_side == -1 else math.nan)

        # bracket exits intrabar
        if pos_side == 1 and not math.isnan(active_long_stop) and not math.isnan(tp_price):
            stop_hit = c.l <= active_long_stop
            tp_hit = c.h >= tp_price
            if stop_hit or tp_hit:
                exit_px = active_long_stop if stop_hit else tp_price
                pnl = (exit_px - entry_price) * pos_qty
                equity_cash += pnl
                trades.append(
                    Trade("long", last_entry_ts, c.ts, entry_price, exit_px, pos_qty, pnl)
                )
                pos_side = 0
                pos_qty = 0.0
                entry_price = math.nan
                sl_price = math.nan
                tp_price = math.nan
                trail_price = math.nan
                bars_in_pos = 0

        if pos_side == -1 and not math.isnan(active_short_stop) and not math.isnan(tp_price):
            stop_hit = c.h >= active_short_stop
            tp_hit = c.l <= tp_price
            if stop_hit or tp_hit:
                exit_px = active_short_stop if stop_hit else tp_price
                pnl = (entry_price - exit_px) * pos_qty
                equity_cash += pnl
                trades.append(
                    Trade("short", last_entry_ts, c.ts, entry_price, exit_px, pos_qty, pnl)
                )
                pos_side = 0
                pos_qty = 0.0
                entry_price = math.nan
                sl_price = math.nan
                tp_price = math.nan
                trail_price = math.nan
                bars_in_pos = 0

        # forced closes (next bar open)
        max_bars_exit = p.use_max_bars and bars_in_pos >= p.max_bars_held
        alignment_loss_long = pos_side == 1 and not bull_aligned
        alignment_loss_short = pos_side == -1 and not bear_aligned
        force_exit = max_bars_exit or alignment_loss_long or alignment_loss_short
        if force_exit and pos_side != 0:
            pending_force_close = True

        # entries (next bar open)
        unrealized = 0.0
        if pos_side == 1:
            unrealized = (c.c - entry_price) * pos_qty
        elif pos_side == -1:
            unrealized = (entry_price - c.c) * pos_qty
        equity_for_risk = equity_cash + unrealized
        risk_dollars = equity_for_risk * (p.risk_per_trade / 100.0)
        stop_distance = atr14[i] * p.sl_atr_mul
        risk_per_unit = stop_distance * 1.0
        raw_qty = (risk_dollars / risk_per_unit) if risk_per_unit > 0 else 0.0
        order_qty = max(p.qty_step, round_qty(raw_qty, p.qty_step))

        long_signal = ready and long_setup and pos_side == 0
        short_signal = ready and short_setup and pos_side == 0
        if long_signal:
            pending_entry = (1, order_qty)
        elif short_signal:
            pending_entry = (-1, order_qty)

        # equity curve for drawdown
        unrealized_end = 0.0
        if pos_side == 1:
            unrealized_end = (c.c - entry_price) * pos_qty
        elif pos_side == -1:
            unrealized_end = (entry_price - c.c) * pos_qty
        equity_curve.append(equity_cash + unrealized_end)

    # close open position at final close
    if pos_side != 0:
        c = candles[-1]
        exit_px = c.c
        pnl = (exit_px - entry_price) * pos_qty if pos_side == 1 else (entry_price - exit_px) * pos_qty
        equity_cash += pnl
        trades.append(
            Trade(
                side="long" if pos_side == 1 else "short",
                entry_ts=last_entry_ts,
                exit_ts=c.ts,
                entry_price=entry_price,
                exit_price=exit_px,
                qty=pos_qty,
                pnl=pnl,
            )
        )
        equity_curve[-1] = equity_cash

    wins = sum(1 for t in trades if t.pnl > 0)
    losses = sum(1 for t in trades if t.pnl < 0)
    gross_win = sum(t.pnl for t in trades if t.pnl > 0)
    gross_loss = abs(sum(t.pnl for t in trades if t.pnl < 0))
    profit_factor = (gross_win / gross_loss) if gross_loss > 0 else float("inf")
    net_profit = equity_cash - 100.0

    peak = equity_curve[0] if equity_curve else 100.0
    max_dd = 0.0
    for e in equity_curve:
        peak = max(peak, e)
        dd = (peak - e) / peak if peak > 0 else 0.0
        max_dd = max(max_dd, dd)

    return {
        "symbol": SYMBOL,
        "timeframe": "1m",
        "bars": len(candles),
        "date_from": datetime.fromtimestamp(candles[0].ts / 1000.0, tz=UTC).isoformat(),
        "date_to": datetime.fromtimestamp(candles[-1].ts / 1000.0, tz=UTC).isoformat(),
        "initial_equity": 100.0,
        "final_equity": equity_cash,
        "net_profit": net_profit,
        "return_pct": (equity_cash / 100.0 - 1.0) * 100.0,
        "trades": len(trades),
        "wins": wins,
        "losses": losses,
        "win_rate_pct": (wins / len(trades) * 100.0) if trades else 0.0,
        "profit_factor": profit_factor,
        "max_drawdown_pct": max_dd * 100.0,
        "params": asdict(p),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Exact-symbol 1m backtest for HYPEUSDT using v2.3.1-style logic.")
    parser.add_argument("--bars", type=int, default=DEFAULT_BARS, help="Number of 1m candles to fetch")
    parser.add_argument("--output", type=Path, default=RESULTS_DIR / "hypeusdt_1m_v23_backtest.json", help="Output JSON path")
    args = parser.parse_args()

    candles = fetch_1m_klines(SYMBOL, args.bars)
    if len(candles) < 1000:
        raise RuntimeError(f"Insufficient candles for {SYMBOL} 1m: got {len(candles)}")

    result = backtest(candles, Params())
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=True, indent=2), encoding="utf-8")

    print("Backtest complete")
    print(f"Symbol: {result['symbol']} | TF: {result['timeframe']}")
    print(f"Bars: {result['bars']} | Trades: {result['trades']} | WinRate: {result['win_rate_pct']:.2f}%")
    print(f"Final Equity: {result['final_equity']:.4f} | Return: {result['return_pct']:.2f}%")
    print(f"MaxDD: {result['max_drawdown_pct']:.2f}% | ProfitFactor: {result['profit_factor']:.4f}")
    print(f"Saved: {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
