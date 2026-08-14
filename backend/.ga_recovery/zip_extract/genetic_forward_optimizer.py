#!/usr/bin/env python3
"""Safety-first genetic forward optimization for the Pionex Pine bot."""

from __future__ import annotations

import json
import math
import random
import statistics
import time
from collections.abc import Sequence
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path

import requests

WORKDIR = Path(__file__).resolve().parent
CACHE_DIR = WORKDIR / "data_cache"
RESULTS_DIR = WORKDIR / "optimizer_results"
BYBIT_BASE_URL = "https://api.bybit.com"

POPULATION_SIZE = 30
GENERATIONS = 50
SURVIVORS = 3
MUTATION_RATE = 0.05
MUTATION_STRENGTH = 0.40
CROSS_THRESHOLD = 0.20
SEED = 42

RAW_INTERVAL_MINUTES = 15
TIMEFRAMES = (15, 30, 60)
FORWARD_FOLDS = ((0.55, 0.70), (0.70, 0.85), (0.85, 1.00))
WARMUP_BARS = 260
FULL_BATCH_SIZE = 12
REFRESH_EVERY = 10
MIN_TURNOVER_USD = 5_000_000.0
MAX_SYMBOLS_FETCH = 36
MAX_FINAL_DATASETS = 72
RAW_BARS_TARGET = 4000
TAKER_FEE = 0.00055
SLIPPAGE = 0.00075
DAILY_LOSS_LIMIT = -0.03
MIN_TRADES_PER_FOLD = 12


@dataclass(frozen=True)
class Candle:
    timestamp: int
    open: float
    high: float
    low: float
    close: float
    volume: float


@dataclass(frozen=True)
class ParameterSet:
    min_conf: int
    sl_atr_mul: float
    tp_atr_mul: float
    vol_mult: float
    max_daily_move_pct: float
    body_factor: float
    body_atr_floor: float
    session_mode: int
    use_shorts: bool
    risk_fraction: float

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


@dataclass
class FoldMetrics:
    net_return: float
    max_drawdown: float
    profit_factor: float
    expectancy: float
    sortino: float
    recovery: float
    trades: int
    win_rate: float
    daily_loss_breaches: int
    robust_return: float


@dataclass
class DatasetScore:
    symbol: str
    timeframe: int
    score: float
    metrics: FoldMetrics


@dataclass
class CandidateResult:
    params: ParameterSet
    fitness: float
    universe_metrics: dict[str, float]
    top_datasets: list[DatasetScore]


class BybitClient:
    def __init__(self) -> None:
        self.session = requests.Session()

    def _get(self, path: str, params: dict[str, object]) -> dict:
        response = self.session.get(f"{BYBIT_BASE_URL}{path}", params=params, timeout=30)
        response.raise_for_status()
        payload = response.json()
        if payload.get("retCode") != 0:
            raise RuntimeError(f"Bybit error: {payload}")
        return payload["result"]

    def fetch_linear_universe(self) -> list[str]:
        instruments = self._get("/v5/market/instruments-info", {"category": "linear", "limit": 1000})["list"]
        tradable = {
            row["symbol"]: row
            for row in instruments
            if row.get("status") == "Trading" and row.get("quoteCoin") == "USDT"
        }
        tickers = self._get("/v5/market/tickers", {"category": "linear"})["list"]
        ranked: list[tuple[str, float]] = []
        for ticker in tickers:
            symbol = ticker["symbol"]
            if symbol not in tradable:
                continue
            turnover = float(ticker.get("turnover24h") or 0.0)
            if turnover >= MIN_TURNOVER_USD:
                ranked.append((symbol, turnover))
        ranked.sort(key=lambda item: item[1], reverse=True)
        symbols = [symbol for symbol, _ in ranked[:MAX_SYMBOLS_FETCH]]
        if "HYPEUSDT" in tradable and "HYPEUSDT" not in symbols:
            symbols.append("HYPEUSDT")
        return symbols

    def fetch_15m_klines(self, symbol: str, bars_target: int = RAW_BARS_TARGET) -> list[Candle]:
        CACHE_DIR.mkdir(exist_ok=True)
        cache_path = CACHE_DIR / f"{symbol}_15m_{bars_target}.json"
        if cache_path.exists():
            return [Candle(**row) for row in json.loads(cache_path.read_text(encoding="utf-8"))]

        bars: list[Candle] = []
        end_ms = int(time.time() * 1000)
        tf_ms = RAW_INTERVAL_MINUTES * 60 * 1000
        while len(bars) < bars_target:
            remaining = bars_target - len(bars)
            limit = min(remaining, 1000)
            result = self._get(
                "/v5/market/kline",
                {
                    "category": "linear",
                    "symbol": symbol,
                    "interval": str(RAW_INTERVAL_MINUTES),
                    "end": end_ms,
                    "limit": limit,
                },
            )["list"]
            if not result:
                break
            chunk = [
                Candle(
                    timestamp=int(row[0]),
                    open=float(row[1]),
                    high=float(row[2]),
                    low=float(row[3]),
                    close=float(row[4]),
                    volume=float(row[5]),
                )
                for row in result
            ]
            chunk.sort(key=lambda candle: candle.timestamp)
            oldest = chunk[0].timestamp
            bars = chunk + bars
            end_ms = oldest - tf_ms
            time.sleep(0.08)
            if len(chunk) < limit:
                break

        deduped: dict[int, Candle] = {candle.timestamp: candle for candle in bars}
        ordered = [deduped[key] for key in sorted(deduped)]
        cache_path.write_text(
            json.dumps([asdict(candle) for candle in ordered], ensure_ascii=True, indent=2),
            encoding="utf-8",
        )
        return ordered


def aggregate_candles(raw_candles: Sequence[Candle], timeframe_minutes: int) -> list[Candle]:
    if timeframe_minutes == RAW_INTERVAL_MINUTES:
        return list(raw_candles)
    bucket_ms = timeframe_minutes * 60 * 1000
    grouped: list[Candle] = []
    current_bucket: int | None = None
    bucket_rows: list[Candle] = []
    for candle in raw_candles:
        bucket = (candle.timestamp // bucket_ms) * bucket_ms
        if current_bucket is None:
            current_bucket = bucket
        if bucket != current_bucket:
            if bucket_rows:
                grouped.append(
                    Candle(
                        timestamp=current_bucket,
                        open=bucket_rows[0].open,
                        high=max(row.high for row in bucket_rows),
                        low=min(row.low for row in bucket_rows),
                        close=bucket_rows[-1].close,
                        volume=sum(row.volume for row in bucket_rows),
                    )
                )
            current_bucket = bucket
            bucket_rows = []
        bucket_rows.append(candle)
    if bucket_rows:
        grouped.append(
            Candle(
                timestamp=current_bucket if current_bucket is not None else bucket_rows[0].timestamp,
                open=bucket_rows[0].open,
                high=max(row.high for row in bucket_rows),
                low=min(row.low for row in bucket_rows),
                close=bucket_rows[-1].close,
                volume=sum(row.volume for row in bucket_rows),
            )
        )
    return grouped


def ema(values: Sequence[float], length: int) -> list[float | None]:
    alpha = 2.0 / (length + 1.0)
    result: list[float | None] = [None] * len(values)
    current: float | None = None
    for idx, value in enumerate(values):
        current = value if current is None else (alpha * value + (1 - alpha) * current)
        result[idx] = current
    return result


def sma(values: Sequence[float], length: int) -> list[float | None]:
    result: list[float | None] = [None] * len(values)
    window_sum = 0.0
    for idx, value in enumerate(values):
        window_sum += value
        if idx >= length:
            window_sum -= values[idx - length]
        if idx >= length - 1:
            result[idx] = window_sum / length
    return result


def atr(candles: Sequence[Candle], length: int = 14) -> list[float | None]:
    tr_values: list[float] = []
    for idx, candle in enumerate(candles):
        if idx == 0:
            tr_values.append(candle.high - candle.low)
        else:
            prev_close = candles[idx - 1].close
            tr_values.append(max(candle.high - candle.low, abs(candle.high - prev_close), abs(candle.low - prev_close)))
    return sma(tr_values, length)


def compute_pivots(candles: Sequence[Candle], left: int = 5, right: int = 5) -> tuple[list[float | None], list[float | None]]:
    ph: list[float | None] = [None] * len(candles)
    pl: list[float | None] = [None] * len(candles)
    for idx in range(left + right, len(candles)):
        pivot_idx = idx - right
        window = candles[pivot_idx - left : pivot_idx + right + 1]
        pivot_high = candles[pivot_idx].high
        pivot_low = candles[pivot_idx].low
        if pivot_high >= max(row.high for row in window):
            ph[idx] = pivot_high
        if pivot_low <= min(row.low for row in window):
            pl[idx] = pivot_low
    return ph, pl


def build_trend_lookup(candles: Sequence[Candle]) -> dict[int, tuple[bool, bool]]:
    closes = [row.close for row in candles]
    ema50 = ema(closes, 50)
    ema200 = ema(closes, 200)
    lookup: dict[int, tuple[bool, bool]] = {}
    for idx, candle in enumerate(candles):
        fast = ema50[idx]
        slow = ema200[idx]
        if fast is None or slow is None:
            lookup[candle.timestamp] = (False, False)
            continue
        lookup[candle.timestamp] = (fast > slow and candle.close > fast, fast < slow and candle.close < fast)
    return lookup


def previous_daily_open_lookup(candles: Sequence[Candle]) -> dict[int, float]:
    day_open: dict[int, float] = {}
    for candle in candles:
        day_bucket = candle.timestamp // 86_400_000
        day_open.setdefault(day_bucket, candle.open)
    lookup: dict[int, float] = {}
    for candle in candles:
        day_bucket = candle.timestamp // 86_400_000
        lookup[candle.timestamp] = day_open.get(day_bucket - 1, day_open.get(day_bucket, candle.open))
    return lookup


def build_closed_state_lookup(candles: Sequence[Candle], trends: dict[int, tuple[bool, bool]], shift_bars: int = 1) -> dict[int, tuple[bool, bool]]:
    ordered = sorted(candles, key=lambda row: row.timestamp)
    timestamps = [row.timestamp for row in ordered]
    shifted: dict[int, tuple[bool, bool]] = {}
    for idx, timestamp in enumerate(timestamps):
        ref_idx = idx - shift_bars
        shifted[timestamp] = trends[timestamps[ref_idx]] if ref_idx >= 0 else (False, False)
    return shifted


def session_allows(session_mode: int, timestamp_ms: int) -> bool:
    dt = datetime.fromtimestamp(timestamp_ms / 1000, tz=UTC)
    hour = dt.hour
    if session_mode == 0:
        return True
    if session_mode == 1:
        return 6 <= hour < 18
    if session_mode == 2:
        return 8 <= hour < 22
    return 12 <= hour < 23


def normalize_score(value: float, scale: float) -> float:
    return 0.0 if scale == 0 else math.tanh(value / scale)


class StrategyEvaluator:
    def __init__(self, raw_by_symbol: dict[str, list[Candle]]) -> None:
        self.raw_by_symbol = raw_by_symbol
        self.dataset_cache: dict[tuple[str, int], dict[str, object]] = {}

    def _prepare_dataset(self, symbol: str, timeframe: int) -> dict[str, object]:
        key = (symbol, timeframe)
        if key in self.dataset_cache:
            return self.dataset_cache[key]

        raw = self.raw_by_symbol[symbol]
        base = aggregate_candles(raw, timeframe)
        h15 = aggregate_candles(raw, 15)
        h60 = aggregate_candles(raw, 60)
        h240 = aggregate_candles(raw, 240)
        dataset = {
            "candles": base,
            "atr": atr(base, 14),
            "vol_ma": sma([row.volume for row in base], 20),
            "pivot_highs": compute_pivots(base)[0],
            "pivot_lows": compute_pivots(base)[1],
            "prev_day_open": previous_daily_open_lookup(base),
            "h15_states": build_closed_state_lookup(h15, build_trend_lookup(h15), shift_bars=1),
            "h60_states": build_closed_state_lookup(h60, build_trend_lookup(h60), shift_bars=1),
            "h240_states": build_closed_state_lookup(h240, build_trend_lookup(h240), shift_bars=1),
        }
        self.dataset_cache[key] = dataset
        return dataset

    def _trend_state(self, states: dict[int, tuple[bool, bool]], candle_ts: int) -> tuple[bool, bool]:
        latest = None
        for timestamp in states:
            if timestamp <= candle_ts and (latest is None or timestamp > latest):
                latest = timestamp
        return states[latest] if latest is not None else (False, False)

    def evaluate_dataset(self, symbol: str, timeframe: int, params: ParameterSet) -> DatasetScore:
        data = self._prepare_dataset(symbol, timeframe)
        candles: list[Candle] = data["candles"]  # type: ignore[assignment]
        if len(candles) < 500:
            metrics = FoldMetrics(0.0, 1.0, 0.0, -1.0, -1.0, -1.0, 0, 0.0, 1, -1.0)
            return DatasetScore(symbol, timeframe, -1.0, metrics)

        fold_scores: list[float] = []
        fold_metrics: list[FoldMetrics] = []
        for start_frac, end_frac in FORWARD_FOLDS:
            start_idx = int(len(candles) * start_frac)
            end_idx = int(len(candles) * end_frac)
            if end_idx - start_idx < 60:
                continue
            metrics = self._simulate_segment(data, params, start_idx, end_idx)
            fold_metrics.append(metrics)
            fold_scores.append(self._score_fold(metrics))

        if not fold_scores:
            metrics = FoldMetrics(0.0, 1.0, 0.0, -1.0, -1.0, -1.0, 0, 0.0, 1, -1.0)
            return DatasetScore(symbol, timeframe, -1.0, metrics)

        summary = FoldMetrics(
            net_return=statistics.mean(x.net_return for x in fold_metrics),
            max_drawdown=max(x.max_drawdown for x in fold_metrics),
            profit_factor=statistics.mean(x.profit_factor for x in fold_metrics),
            expectancy=statistics.mean(x.expectancy for x in fold_metrics),
            sortino=statistics.mean(x.sortino for x in fold_metrics),
            recovery=statistics.mean(x.recovery for x in fold_metrics),
            trades=sum(x.trades for x in fold_metrics),
            win_rate=statistics.mean(x.win_rate for x in fold_metrics),
            daily_loss_breaches=sum(x.daily_loss_breaches for x in fold_metrics),
            robust_return=statistics.mean(x.robust_return for x in fold_metrics),
        )
        return DatasetScore(symbol, timeframe, statistics.mean(fold_scores), summary)

    def _simulate_segment(self, data: dict[str, object], params: ParameterSet, start_idx: int, end_idx: int) -> FoldMetrics:
        candles: list[Candle] = data["candles"]  # type: ignore[assignment]
        atr_values: list[float | None] = data["atr"]  # type: ignore[assignment]
        vol_ma: list[float | None] = data["vol_ma"]  # type: ignore[assignment]
        pivot_highs: list[float | None] = data["pivot_highs"]  # type: ignore[assignment]
        pivot_lows: list[float | None] = data["pivot_lows"]  # type: ignore[assignment]
        prev_day_open: dict[int, float] = data["prev_day_open"]  # type: ignore[assignment]
        h15_states: dict[int, tuple[bool, bool]] = data["h15_states"]  # type: ignore[assignment]
        h60_states: dict[int, tuple[bool, bool]] = data["h60_states"]  # type: ignore[assignment]
        h240_states: dict[int, tuple[bool, bool]] = data["h240_states"]  # type: ignore[assignment]

        begin = max(2, start_idx - WARMUP_BARS)
        equity = 1.0
        equity_curve: list[float] = []
        trade_returns: list[float] = []
        daily_returns: dict[int, float] = {}

        position = 0
        entry_price = 0.0
        active_sl = 0.0
        active_tp = 0.0
        last_ph: float | None = None
        last_pl: float | None = None

        for idx in range(begin, end_idx):
            candle = candles[idx]
            atr_value = atr_values[idx]
            vol_avg = vol_ma[idx]
            if atr_value is None or vol_avg is None:
                continue
            if pivot_highs[idx] is not None:
                last_ph = pivot_highs[idx]
            if pivot_lows[idx] is not None:
                last_pl = pivot_lows[idx]

            atr_safe = max(atr_value, candle.close * 0.0001)
            is_vol_high = candle.volume > vol_avg * params.vol_mult
            h4_bull, h4_bear = self._trend_state(h240_states, candle.timestamp)
            h1_bull, h1_bear = self._trend_state(h60_states, candle.timestamp)
            m15_bull, m15_bear = self._trend_state(h15_states, candle.timestamp)

            prev_close = candles[idx - 1].close
            body_curr = abs(candle.close - candle.open)
            body_prev = abs(candles[idx - 1].close - candles[idx - 1].open)
            body_min = max(body_prev, atr_safe * params.body_atr_floor)

            cisd_bull = last_ph is not None and prev_close <= last_ph and candle.close > last_ph
            cisd_bear = last_pl is not None and prev_close >= last_pl and candle.close < last_pl
            ob_bull = candles[idx - 1].close < candles[idx - 1].open and candle.close > candle.open and body_curr > body_min * params.body_factor
            ob_bear = candles[idx - 1].close > candles[idx - 1].open and candle.close < candle.open and body_curr > body_min * params.body_factor
            fvg_bull = idx >= 2 and candle.low > candles[idx - 2].high and candles[idx - 1].close > candles[idx - 1].open
            fvg_bear = idx >= 2 and candle.high < candles[idx - 2].low and candles[idx - 1].close < candles[idx - 1].open

            score_long = 0
            score_short = 0
            score_long += 10 if h4_bull else 0
            score_short += 10 if h4_bear else 0
            score_long += 10 if h1_bull else 0
            score_short += 10 if h1_bear else 0
            score_long += 10 if m15_bull else 0
            score_short += 10 if m15_bear else 0
            score_long += 20 if cisd_bull else 0
            score_short += 20 if cisd_bear else 0
            score_long += 10 if ob_bull else 0
            score_short += 10 if ob_bear else 0
            score_long += 10 if fvg_bull else 0
            score_short += 10 if fvg_bear else 0
            score_long += 10 if is_vol_high else 0
            score_short += 10 if is_vol_high else 0

            daily_move = abs(candle.close - prev_day_open[candle.timestamp]) / prev_day_open[candle.timestamp] * 100.0
            in_session = session_allows(params.session_mode, candle.timestamp)
            block_long = (not in_session) or daily_move >= params.max_daily_move_pct
            block_short = (not in_session) or daily_move >= params.max_daily_move_pct
            long_setup = score_long >= params.min_conf and not block_long and position == 0
            short_setup = score_short >= params.min_conf and not block_short and params.use_shorts and position == 0

            if position == 1:
                stop_hit = candle.low <= active_sl
                target_hit = candle.high >= active_tp
                blocker_hit = block_long
                reverse_hit = score_short >= params.min_conf and not block_short and params.use_shorts
                if stop_hit or target_hit or blocker_hit or reverse_hit:
                    if idx >= start_idx:
                        exit_price = active_sl if stop_hit else active_tp if target_hit else candle.close
                        trade_ret = ((exit_price - entry_price) / entry_price - (TAKER_FEE * 2 + SLIPPAGE)) * params.risk_fraction
                        equity *= 1.0 + trade_ret
                        trade_returns.append(trade_ret)
                        day_key = candle.timestamp // 86_400_000
                        daily_returns[day_key] = daily_returns.get(day_key, 0.0) + trade_ret
                    position = 0

            if position == -1:
                stop_hit = candle.high >= active_sl
                target_hit = candle.low <= active_tp
                blocker_hit = block_short
                reverse_hit = score_long >= params.min_conf and not block_long
                if stop_hit or target_hit or blocker_hit or reverse_hit:
                    if idx >= start_idx:
                        exit_price = active_sl if stop_hit else active_tp if target_hit else candle.close
                        trade_ret = ((entry_price - exit_price) / entry_price - (TAKER_FEE * 2 + SLIPPAGE)) * params.risk_fraction
                        equity *= 1.0 + trade_ret
                        trade_returns.append(trade_ret)
                        day_key = candle.timestamp // 86_400_000
                        daily_returns[day_key] = daily_returns.get(day_key, 0.0) + trade_ret
                    position = 0

            if idx >= start_idx and position == 0:
                if long_setup:
                    position = 1
                    entry_price = candle.close * (1 + SLIPPAGE * 0.5)
                    active_sl = candle.close - atr_safe * params.sl_atr_mul
                    active_tp = candle.close + atr_safe * params.tp_atr_mul
                elif short_setup:
                    position = -1
                    entry_price = candle.close * (1 - SLIPPAGE * 0.5)
                    active_sl = candle.close + atr_safe * params.sl_atr_mul
                    active_tp = candle.close - atr_safe * params.tp_atr_mul

            equity_curve.append(equity)

        if position != 0 and end_idx > start_idx:
            last = candles[end_idx - 1]
            exit_price = last.close
            if position == 1:
                trade_ret = ((exit_price - entry_price) / entry_price - (TAKER_FEE * 2 + SLIPPAGE)) * params.risk_fraction
            else:
                trade_ret = ((entry_price - exit_price) / entry_price - (TAKER_FEE * 2 + SLIPPAGE)) * params.risk_fraction
            equity *= 1.0 + trade_ret
            trade_returns.append(trade_ret)
            day_key = last.timestamp // 86_400_000
            daily_returns[day_key] = daily_returns.get(day_key, 0.0) + trade_ret
            equity_curve.append(equity)

        max_dd = 0.0
        peak = 1.0
        for point in equity_curve:
            peak = max(peak, point)
            max_dd = max(max_dd, (peak - point) / peak if peak else 0.0)
        gross_profit = sum(x for x in trade_returns if x > 0)
        gross_loss = abs(sum(x for x in trade_returns if x < 0))
        profit_factor = gross_profit / gross_loss if gross_loss > 0 else 9.99 if gross_profit > 0 else 0.0
        expectancy = statistics.mean(trade_returns) if trade_returns else -1.0
        downside = [ret for ret in trade_returns if ret < 0]
        downside_dev = math.sqrt(sum(ret * ret for ret in downside) / len(downside)) if downside else 0.0001
        sortino = expectancy / downside_dev if trade_returns else -1.0
        recovery = (equity - 1.0) / max(max_dd, 1e-6)
        wins = sum(1 for ret in trade_returns if ret > 0)
        win_rate = wins / len(trade_returns) if trade_returns else 0.0
        robust_return = sum(ret - 0.0008 for ret in trade_returns)
        daily_breaches = sum(1 for value in daily_returns.values() if value <= DAILY_LOSS_LIMIT)
        return FoldMetrics(equity - 1.0, max_dd, profit_factor, expectancy, sortino, recovery, len(trade_returns), win_rate, daily_breaches, robust_return)

    def _score_fold(self, metrics: FoldMetrics) -> float:
        if metrics.max_drawdown > 0.08 or metrics.daily_loss_breaches > 0 or metrics.profit_factor < 1.15 or metrics.expectancy <= 0 or metrics.trades < MIN_TRADES_PER_FOLD or metrics.robust_return <= 0:
            return -1.0
        robust_score = (
            0.25 * normalize_score(metrics.net_return, 0.35)
            + 0.20 * normalize_score(metrics.expectancy, 0.01)
            + 0.15 * normalize_score(metrics.sortino, 2.5)
            + 0.15 * normalize_score(metrics.recovery, 3.5)
            + 0.10 * normalize_score(max(0.0, metrics.profit_factor - 1.0), 1.0)
            + 0.10 * normalize_score(metrics.win_rate, 0.65)
            + 0.05 * normalize_score(metrics.robust_return, 0.25)
        )
        drawdown_penalty = max(0.0, (metrics.max_drawdown - 0.05) / 0.05) ** 2
        tail_penalty = max(0.0, (0.4 - metrics.win_rate) / 0.4) if metrics.trades else 1.0
        overtrade_penalty = max(0.0, (metrics.trades - 80) / 80)
        return robust_score - drawdown_penalty - tail_penalty - overtrade_penalty


class GeneticOptimizer:
    def __init__(self, evaluator: StrategyEvaluator, datasets: list[tuple[str, int]], seed: int = SEED) -> None:
        self.evaluator = evaluator
        self.datasets = datasets
        self.rng = random.Random(seed)

    def random_params(self) -> ParameterSet:
        return ParameterSet(
            min_conf=self.rng.randint(68, 90),
            sl_atr_mul=round(self.rng.uniform(1.0, 2.4), 2),
            tp_atr_mul=round(self.rng.uniform(3.2, 7.0), 2),
            vol_mult=round(self.rng.uniform(1.1, 2.1), 2),
            max_daily_move_pct=round(self.rng.uniform(5.0, 14.0), 1),
            body_factor=round(self.rng.uniform(1.3, 2.1), 2),
            body_atr_floor=round(self.rng.uniform(0.08, 0.24), 2),
            session_mode=self.rng.randint(0, 3),
            use_shorts=self.rng.choice([True, True, True, False]),
            risk_fraction=round(self.rng.uniform(0.45, 1.0), 2),
        )

    def mutate(self, params: ParameterSet) -> ParameterSet:
        values = params.to_dict()
        bounds = {
            "min_conf": (68, 90),
            "sl_atr_mul": (1.0, 2.4),
            "tp_atr_mul": (3.2, 7.0),
            "vol_mult": (1.1, 2.1),
            "max_daily_move_pct": (5.0, 14.0),
            "body_factor": (1.3, 2.1),
            "body_atr_floor": (0.08, 0.24),
            "session_mode": (0, 3),
            "risk_fraction": (0.45, 1.0),
        }
        for key, (low, high) in bounds.items():
            if self.rng.random() < MUTATION_RATE:
                if isinstance(low, int):
                    span = max(1, round((high - low) * MUTATION_STRENGTH))
                    shifted = int(values[key]) + self.rng.randint(-span, span)  # type: ignore[arg-type]
                    values[key] = max(low, min(high, shifted))
                else:
                    span = (high - low) * MUTATION_STRENGTH
                    shifted = float(values[key]) + self.rng.uniform(-span, span)  # type: ignore[arg-type]
                    values[key] = round(max(low, min(high, shifted)), 2)
        if self.rng.random() < MUTATION_RATE:
            values["use_shorts"] = not bool(values["use_shorts"])
        return ParameterSet(**values)  # type: ignore[arg-type]

    def crossover(self, left: ParameterSet, right: ParameterSet) -> ParameterSet:
        child: dict[str, object] = {}
        bounds = {
            "min_conf": (68, 90),
            "sl_atr_mul": (1.0, 2.4),
            "tp_atr_mul": (3.2, 7.0),
            "vol_mult": (1.1, 2.1),
            "max_daily_move_pct": (5.0, 14.0),
            "body_factor": (1.3, 2.1),
            "body_atr_floor": (0.08, 0.24),
            "session_mode": (0, 3),
            "risk_fraction": (0.45, 1.0),
        }
        left_dict = left.to_dict()
        right_dict = right.to_dict()
        for key, (low, high) in bounds.items():
            lval = left_dict[key]
            rval = right_dict[key]
            if isinstance(low, int):
                denom = max(1, high - low)
                distance = abs(int(lval) - int(rval)) / denom
                if distance < CROSS_THRESHOLD:
                    child[key] = lval if self.rng.random() < 0.65 else rval
                else:
                    child[key] = round((int(lval) + int(rval)) / 2)
            else:
                denom = high - low
                distance = abs(float(lval) - float(rval)) / denom
                if distance < CROSS_THRESHOLD:
                    child[key] = lval if self.rng.random() < 0.65 else rval
                else:
                    mix = self.rng.uniform(0.35, 0.65)
                    child[key] = round(float(lval) * mix + float(rval) * (1 - mix), 2)
        child["use_shorts"] = left.use_shorts if self.rng.random() < 0.5 else right.use_shorts
        return ParameterSet(**child)  # type: ignore[arg-type]

    def evaluate_candidate(self, params: ParameterSet, dataset_batch: Sequence[tuple[str, int]]) -> CandidateResult:
        dataset_scores = [self.evaluator.evaluate_dataset(symbol, timeframe, params) for symbol, timeframe in dataset_batch]
        valid_scores = [row.score for row in dataset_scores if row.score > -1]
        if not valid_scores:
            return CandidateResult(params, -1.0, {"datasets": 0.0}, [])
        sorted_scores = sorted(valid_scores)
        p25 = sorted_scores[max(0, int(len(sorted_scores) * 0.25) - 1)]
        fitness = (
            0.40 * statistics.median(valid_scores)
            + 0.25 * p25
            + 0.20 * min(valid_scores)
            + 0.15 * statistics.mean(valid_scores)
        )
        metrics = {
            "datasets": float(len(valid_scores)),
            "median_score": statistics.median(valid_scores),
            "p25_score": p25,
            "min_score": min(valid_scores),
            "mean_score": statistics.mean(valid_scores),
            "median_return": statistics.median(row.metrics.net_return for row in dataset_scores),
            "median_dd": statistics.median(row.metrics.max_drawdown for row in dataset_scores),
            "median_pf": statistics.median(row.metrics.profit_factor for row in dataset_scores),
            "median_trades": statistics.median(row.metrics.trades for row in dataset_scores),
        }
        return CandidateResult(params, fitness, metrics, sorted(dataset_scores, key=lambda row: row.score, reverse=True)[:5])

    def generation_batch(self, generation: int) -> list[tuple[str, int]]:
        if generation % REFRESH_EVERY == 0:
            self.rng.shuffle(self.datasets)
        return self.datasets[: min(FULL_BATCH_SIZE, len(self.datasets))]

    def optimize(self) -> tuple[list[CandidateResult], list[dict[str, object]]]:
        population = [self.random_params() for _ in range(POPULATION_SIZE)]
        history: list[dict[str, object]] = []
        elites: list[CandidateResult] = []
        for generation in range(1, GENERATIONS + 1):
            batch = self.generation_batch(generation)
            results = [self.evaluate_candidate(candidate, batch) for candidate in population]
            results.sort(key=lambda row: row.fitness, reverse=True)
            elites = results[:SURVIVORS]
            history.append({
                "generation": generation,
                "best_fitness": elites[0].fitness,
                "median_fitness": statistics.median(row.fitness for row in results),
                "batch_size": len(batch),
                "best_params": elites[0].params.to_dict(),
            })
            next_population = [elite.params for elite in elites]
            while len(next_population) < POPULATION_SIZE:
                parent_a = self.rng.choice(elites).params
                parent_b = self.rng.choice(elites).params
                next_population.append(self.mutate(self.crossover(parent_a, parent_b)))
            population = next_population

        unique_candidates: list[ParameterSet] = []
        seen = set()
        for elite in elites:
            key = tuple(elite.params.to_dict().items())
            if key not in seen:
                unique_candidates.append(elite.params)
                seen.add(key)
        while len(unique_candidates) < 12:
            unique_candidates.append(self.random_params())

        final_batch = self.datasets[: min(MAX_FINAL_DATASETS, len(self.datasets))]
        final_results = [self.evaluate_candidate(candidate, final_batch) for candidate in unique_candidates]
        final_results.sort(key=lambda row: row.fitness, reverse=True)
        return final_results[:3], history


def write_report(path: Path, top_results: Sequence[CandidateResult], symbols: Sequence[str], datasets: Sequence[tuple[str, int]], history: Sequence[dict[str, object]]) -> None:
    lines = [
        "# Genetic Forward Optimization Report",
        "",
        f"- Erstellt: `{datetime.now(UTC).isoformat()}`",
        "- Datenquelle: `Bybit linear USDT perpetuals`",
        f"- Universum: `{len(symbols)} Symbole / {len(datasets)} Datasets`",
        "- Timeframes: `15m`, `30m`, `1h`",
        "- Genetic Setup: `30 Population`, `50 Generationen`, `Top 3 survive`, `5% Mutation`, `40% Mutationsstärke`, `20% Crossover-Threshold`",
        "- Safety Gates: `MaxDD <= 8%`, `keine Daily-Loss-Breaches`, `PF >= 1.15`, `Expectancy > 0`",
        "",
        "## Top 3 Ergebnisse",
        "",
    ]
    for rank, result in enumerate(top_results, start=1):
        best_dataset = result.top_datasets[0] if result.top_datasets else None
        lines.extend([
            f"### Rank {rank}",
            "",
            f"- Fitness: `{result.fitness:.4f}`",
            f"- Median Return: `{result.universe_metrics.get('median_return', 0.0) * 100:.2f}%`",
            f"- Median MaxDD: `{result.universe_metrics.get('median_dd', 0.0) * 100:.2f}%`",
            f"- Median Profit Factor: `{result.universe_metrics.get('median_pf', 0.0):.2f}`",
            f"- Median Trades: `{result.universe_metrics.get('median_trades', 0.0):.0f}`",
        ])
        if best_dataset is not None:
            lines.extend([
                f"- Bestes Dataset: `{best_dataset.symbol} / {best_dataset.timeframe}m`",
                f"- Dataset Score: `{best_dataset.score:.4f}`",
            ])
        lines.extend(["", "| Parameter | Wert |", "| --- | --- |"])
        for key, value in result.params.to_dict().items():
            lines.append(f"| `{key}` | `{value}` |")
        lines.append("")
    lines.extend([
        "## Laufnotizen",
        "",
        "- Bewertet wurde mit konservativen Bar-Close-Fills und SL-vor-TP bei gleicher Kerze.",
        "- H4/H1/M15-Zustaende sind absichtlich verzoegert modelliert, um die Pine-Logik nicht zu beschoenigen.",
        "- Das Universum ist liquiditaetsgefiltert (`turnover24h >= 5M USD`).",
        "- `HYPEUSDT` wird explizit im Universum behalten.",
        "",
        "## Generationsverlauf",
        "",
        "| Generation | Best Fitness | Median Fitness |",
        "| --- | --- | --- |",
    ])
    for row in history:
        lines.append(f"| `{row['generation']}` | `{row['best_fitness']:.4f}` | `{row['median_fitness']:.4f}` |")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    random.seed(SEED)
    CACHE_DIR.mkdir(exist_ok=True)
    RESULTS_DIR.mkdir(exist_ok=True)
    client = BybitClient()
    symbols = client.fetch_linear_universe()
    raw_by_symbol = {symbol: client.fetch_15m_klines(symbol) for symbol in symbols}
    raw_by_symbol = {symbol: bars for symbol, bars in raw_by_symbol.items() if len(bars) >= 1500}
    if "HYPEUSDT" not in raw_by_symbol:
        raise RuntimeError("HYPEUSDT konnte nicht mit genug Historie geladen werden.")
    evaluator = StrategyEvaluator(raw_by_symbol)
    datasets = [(symbol, timeframe) for symbol in raw_by_symbol for timeframe in TIMEFRAMES]
    optimizer = GeneticOptimizer(evaluator, datasets)
    top_results, history = optimizer.optimize()

    timestamp = datetime.now(UTC).strftime("%Y%m%d_%H%M%S")
    report_path = RESULTS_DIR / f"genetic_forward_optimization_report_{timestamp}.md"
    json_path = RESULTS_DIR / f"genetic_forward_optimization_report_{timestamp}.json"
    write_report(report_path, top_results, list(raw_by_symbol), datasets, history)
    json_path.write_text(json.dumps({
        "created_at": datetime.now(UTC).isoformat(),
        "symbols": list(raw_by_symbol),
        "datasets": [{"symbol": symbol, "timeframe": timeframe} for symbol, timeframe in datasets],
        "top_results": [
            {
                "fitness": result.fitness,
                "params": result.params.to_dict(),
                "universe_metrics": result.universe_metrics,
                "top_datasets": [
                    {
                        "symbol": dataset.symbol,
                        "timeframe": dataset.timeframe,
                        "score": dataset.score,
                        "metrics": asdict(dataset.metrics),
                    }
                    for dataset in result.top_datasets
                ],
            }
            for result in top_results
        ],
        "history": history,
    }, ensure_ascii=True, indent=2), encoding="utf-8")

    print(f"Report geschrieben: {report_path}")
    print(f"JSON geschrieben:   {json_path}")
    for idx, result in enumerate(top_results, start=1):
        print(f"{idx}. Fitness={result.fitness:.4f} Params={result.params.to_dict()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
