"""Genetic forward optimizer engine (recovered from ga_forward_optimizer.py).

Pipeline: symbols → 15m klines → resample 30m/1h → CISD/trend/FVG features →
train/forward split → GA → top3. Fitness is safety-biased (few trades → −100).
"""

from __future__ import annotations

import math
import random
import statistics
import time
from collections.abc import Callable, Sequence
from dataclasses import asdict, dataclass
from typing import Any, cast

ProgressCallback = Callable[[dict[str, Any]], None]
Frame = dict[str, object]
SymbolPack = dict[str, Frame]
MarketPacks = dict[str, SymbolPack]


@dataclass(frozen=True)
class Candle:
    ts: int
    o: float
    h: float
    low: float
    c: float
    v: float


@dataclass(frozen=True)
class Genome:
    min_conf: int
    risk_pct: float
    sl_atr_mul: float
    tp_atr_mul: float
    vol_mult: float
    max_daily_move_pct: float
    ob_body_mult: float
    cisd_len: int
    w_trend: int
    w_cisd: int
    w_ob: int
    w_fvg: int
    w_vol: int
    allow_shorts: bool


@dataclass
class Stats:
    trades: int = 0
    wins: int = 0
    losses: int = 0
    net_r: float = 0.0
    gross_win_r: float = 0.0
    gross_loss_r: float = 0.0
    equity: float = 100.0
    peak: float = 100.0
    max_dd: float = 0.0
    max_loss_streak: int = 0
    _streak: int = 0
    returns: list[float] | None = None

    def __post_init__(self) -> None:
        if self.returns is None:
            self.returns = []


def clamp(x: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, x))


def qmean(xs: Sequence[float]) -> float:
    return statistics.fmean(xs) if xs else 0.0


def qstdev(xs: Sequence[float]) -> float:
    return statistics.pstdev(xs) if len(xs) > 1 else 0.0


def resample(candles: list[Candle], factor: int) -> list[Candle]:
    if factor == 1:
        return candles[:]
    out: list[Candle] = []
    for i in range(0, len(candles), factor):
        chunk = candles[i : i + factor]
        if len(chunk) < factor:
            break
        out.append(
            Candle(
                chunk[-1].ts,
                chunk[0].o,
                max(x.h for x in chunk),
                min(x.low for x in chunk),
                chunk[-1].c,
                sum(x.v for x in chunk),
            )
        )
    return out


def ema(xs: Sequence[float], period: int) -> list[float]:
    if not xs:
        return []
    a = 2.0 / (period + 1.0)
    out = [xs[0]]
    for x in xs[1:]:
        out.append(out[-1] * (1.0 - a) + x * a)
    return out


def sma(xs: Sequence[float], period: int) -> list[float]:
    out: list[float] = []
    s = 0.0
    for i, x in enumerate(xs):
        s += x
        if i >= period:
            s -= xs[i - period]
        out.append(s / min(i + 1, period))
    return out


def atr(candles: Sequence[Candle], period: int = 14) -> list[float]:
    trs: list[float] = []
    prev = candles[0].c
    for c in candles:
        trs.append(max(c.h - c.low, abs(c.h - prev), abs(c.low - prev)))
        prev = c.c
    return ema(trs, period)


def trend_flags(candles: Sequence[Candle]) -> tuple[list[bool], list[bool]]:
    closes = [c.c for c in candles]
    e50 = ema(closes, 50)
    e200 = ema(closes, 200)
    bull = [c > a > b for c, a, b in zip(closes, e50, e200)]
    bear = [c < a < b for c, a, b in zip(closes, e50, e200)]
    return bull, bear


def cisd_flags(candles: Sequence[Candle], lr: int) -> tuple[list[bool], list[bool]]:
    n = len(candles)
    bull = [False] * n
    bear = [False] * n
    last_ph = None
    last_pl = None
    for i in range(lr, n - lr):
        h = candles[i].h
        low = candles[i].low
        if all(candles[j].h <= h for j in range(i - lr, i + lr + 1)):
            last_ph = h
        if all(candles[j].low >= low for j in range(i - lr, i + lr + 1)):
            last_pl = low
        if last_ph is not None and candles[i - 1].c <= last_ph < candles[i].c:
            bull[i] = True
        if last_pl is not None and candles[i - 1].c >= last_pl > candles[i].c:
            bear[i] = True
    return bull, bear


def build_frame(
    symbol: str, tf: str, candles: list[Candle], quote_vol: float, cisd_lens: list[int]
) -> Frame:
    bull, bear = trend_flags(candles)
    vols = [c.v for c in candles]
    vol_ma = sma(vols, 20)
    atr14 = atr(candles)
    body_ratio: list[float] = []
    fvg_bull = [False] * len(candles)
    fvg_bear = [False] * len(candles)
    daily_move = [0.0] * len(candles)
    bull_rev = [False] * len(candles)
    bear_rev = [False] * len(candles)
    by_day: dict[str, float] = {}
    for c in candles:
        day = time.strftime("%Y-%m-%d", time.gmtime(c.ts / 1000))
        by_day.setdefault(day, c.o)
    for i in range(len(candles)):
        if i < 2:
            body_ratio.append(0.0)
            continue
        p = candles[i - 1]
        cur = candles[i]
        prev_body = abs(p.c - p.o)
        cur_body = abs(cur.c - cur.o)
        base = max(prev_body, atr14[i] * 0.15, 1e-12)
        body_ratio.append(cur_body / base)
        bull_rev[i] = p.c < p.o and cur.c > cur.o
        bear_rev[i] = p.c > p.o and cur.c < cur.o
        fvg_bull[i] = cur.low > candles[i - 2].h and p.c > p.o
        fvg_bear[i] = cur.h < candles[i - 2].low and p.c < p.o
        day = time.strftime("%Y-%m-%d", time.gmtime(cur.ts / 1000))
        daily_move[i] = abs(cur.c - by_day[day]) / max(by_day[day], 1e-12) * 100.0
    cisd_bull_map: dict[int, list[bool]] = {}
    cisd_bear_map: dict[int, list[bool]] = {}
    for lr in cisd_lens:
        b, s = cisd_flags(candles, lr)
        cisd_bull_map[lr] = b
        cisd_bear_map[lr] = s
    return {
        "symbol": symbol,
        "tf": tf,
        "quote_vol": quote_vol,
        "candles": candles,
        "trend_bull": bull,
        "trend_bear": bear,
        "vol_ratio": [v / m if m else 0.0 for v, m in zip(vols, vol_ma)],
        "atr": atr14,
        "body_ratio": body_ratio,
        "bull_rev": bull_rev,
        "bear_rev": bear_rev,
        "fvg_bull": fvg_bull,
        "fvg_bear": fvg_bear,
        "daily_move": daily_move,
        "cisd_bull": cisd_bull_map,
        "cisd_bear": cisd_bear_map,
        "times": [c.ts for c in candles],
    }


def build_symbol_pack(
    symbol: str, candles_15: list[Candle], quote_vol: float, cisd_lens: list[int] | None = None
) -> SymbolPack:
    lenses = cisd_lens or [3, 4, 5, 6, 7, 8]
    candles_30 = resample(candles_15, 2)
    candles_1h = resample(candles_15, 4)
    return {
        "15m": build_frame(symbol, "15m", candles_15, quote_vol, lenses),
        "30m": build_frame(symbol, "30m", candles_30, quote_vol, lenses),
        "1h": build_frame(symbol, "1h", candles_1h, quote_vol, lenses),
    }


def split_index(n: int, ratio: float) -> int:
    """Train/forward cut. Keeps a usable forward window even on short series."""
    if n <= 0:
        return 0
    if n < 150:
        cut = int(n * ratio)
        return max(20, min(n - 10, cut))
    return max(100, min(n - 50, int(n * ratio)))


def dataset_stats(
    rows: Frame, g: Genome, fee_r: float, max_hold: int, split: int
) -> tuple[Stats, Stats]:
    def run_segment(start: int, end: int) -> Stats:
        s = Stats()
        candles = cast(list[Candle], rows["candles"])
        trend_bull = cast(list[bool], rows["trend_bull"])
        trend_bear = cast(list[bool], rows["trend_bear"])
        vol_ratio = cast(list[float], rows["vol_ratio"])
        atr_vals = cast(list[float], rows["atr"])
        body_ratio = cast(list[float], rows["body_ratio"])
        bull_rev = cast(list[bool], rows["bull_rev"])
        bear_rev = cast(list[bool], rows["bear_rev"])
        fvg_bull = cast(list[bool], rows["fvg_bull"])
        fvg_bear = cast(list[bool], rows["fvg_bear"])
        daily_move = cast(list[float], rows["daily_move"])
        cisd_bull_map = cast(dict[int, list[bool]], rows["cisd_bull"])
        cisd_bear_map = cast(dict[int, list[bool]], rows["cisd_bear"])

        pos = 0
        entry = sl = tp = 0.0
        bars = 0

        for i in range(max(start + 2, 2), end):
            c = candles[i]
            atr_i = max(atr_vals[i], c.c * 0.0001)
            long_score = 0
            short_score = 0
            if trend_bull[i]:
                long_score += g.w_trend
            if trend_bear[i]:
                short_score += g.w_trend
            if cisd_bull_map[g.cisd_len][i]:
                long_score += g.w_cisd
            if cisd_bear_map[g.cisd_len][i]:
                short_score += g.w_cisd
            if bull_rev[i] and body_ratio[i] > g.ob_body_mult:
                long_score += g.w_ob
            if bear_rev[i] and body_ratio[i] > g.ob_body_mult:
                short_score += g.w_ob
            if fvg_bull[i]:
                long_score += g.w_fvg
            if fvg_bear[i]:
                short_score += g.w_fvg
            if vol_ratio[i] > g.vol_mult:
                long_score += g.w_vol
                short_score += g.w_vol

            block = daily_move[i] >= g.max_daily_move_pct
            long_setup = pos == 0 and not block and long_score >= g.min_conf
            short_setup = pos == 0 and not block and g.allow_shorts and short_score >= g.min_conf

            if pos != 0:
                bars += 1
                stop_hit = c.low <= sl if pos == 1 else c.h >= sl
                tp_hit = c.h >= tp if pos == 1 else c.low <= tp
                reverse_hit = (pos == 1 and short_score >= g.min_conf) or (
                    pos == -1 and long_score >= g.min_conf
                )
                exit_hit = stop_hit or tp_hit or block or reverse_hit or bars >= max_hold
                if exit_hit:
                    exit_px = sl if stop_hit else tp if tp_hit else c.c
                    r = (
                        (exit_px - entry) / max(entry - sl, 1e-12)
                        if pos == 1
                        else (entry - exit_px) / max(sl - entry, 1e-12)
                    )
                    r -= fee_r
                    s.trades += 1
                    s.net_r += r
                    assert s.returns is not None
                    s.returns.append(r)
                    if r >= 0:
                        s.wins += 1
                        s.gross_win_r += r
                        s._streak = 0
                    else:
                        s.losses += 1
                        s.gross_loss_r += abs(r)
                        s._streak += 1
                        s.max_loss_streak = max(s.max_loss_streak, s._streak)
                    s.equity *= max(0.0, 1.0 + g.risk_pct * r)
                    s.peak = max(s.peak, s.equity)
                    s.max_dd = max(s.max_dd, (s.peak - s.equity) / max(s.peak, 1e-12) * 100.0)
                    pos = 0
                    bars = 0
                continue

            if long_setup:
                pos = 1
                entry = c.c
                sl = c.c - atr_i * g.sl_atr_mul
                tp = c.c + atr_i * g.tp_atr_mul
                bars = 0
            elif short_setup:
                pos = -1
                entry = c.c
                sl = c.c + atr_i * g.sl_atr_mul
                tp = c.c - atr_i * g.tp_atr_mul
                bars = 0
        return s

    n = len(rows["candles"])  # type: ignore[arg-type]
    split_i = max(0, min(split, n))
    return run_segment(0, split_i), run_segment(split_i, n)


def bundle(s: Stats) -> dict[str, float]:
    if s.trades == 0:
        return {
            "trades": 0,
            "net": -1.0,
            "pf": 0.0,
            "wr": 0.0,
            "dd": 100.0,
            "sharpe": -5.0,
            "consistency": 0.0,
            "streak": float(s.max_loss_streak),
        }
    assert s.returns is not None
    net = (s.equity - 100.0) / 100.0 * 100.0
    wr = s.wins / s.trades * 100.0
    pf = s.gross_win_r / max(s.gross_loss_r, 1e-12)
    avg = qmean(s.returns)
    sd = qstdev(s.returns)
    sharpe = avg / sd * math.sqrt(s.trades) if sd > 0 else (2.0 if avg > 0 else -2.0)
    consistency = 1.0 - min(1.0, abs(s.wins - s.losses) / max(s.trades, 1))
    return {
        "trades": s.trades,
        "net": net,
        "pf": pf,
        "wr": wr,
        "dd": s.max_dd,
        "sharpe": sharpe,
        "consistency": consistency,
        "streak": float(s.max_loss_streak),
    }


def fitness(b: dict[str, float]) -> float:
    """Safety-biased fitness: trades < 10 → −100; DD/PF penalties as original."""
    if b["trades"] < 10:
        return -100.0
    score = 0.24 * clamp(b["net"] / 100.0, -1.0, 5.0)
    score += 0.20 * clamp((b["pf"] - 1.0) / 1.5, 0.0, 1.0)
    score += 0.22 * clamp(1.0 - b["dd"] / 12.0, 0.0, 1.0)
    score += 0.14 * clamp((b["sharpe"] + 1.0) / 4.0, 0.0, 1.0)
    score += 0.10 * clamp((b["wr"] - 45.0) / 25.0, 0.0, 1.0)
    score += 0.05 * clamp(b["consistency"], 0.0, 1.0)
    score += 0.05 * clamp(1.0 - b["streak"] / 8.0, 0.0, 1.0)
    if b["dd"] > 12.0:
        score *= 0.35
    if b["dd"] > 18.0:
        score *= 0.15
    if b["pf"] < 1.05:
        score *= 0.5
    return score


def genome_dict(g: Genome) -> dict[str, object]:
    return asdict(g)


def random_genome(rng: random.Random) -> Genome:
    return Genome(
        min_conf=rng.randint(42, 72),
        risk_pct=rng.uniform(0.0025, 0.0075),
        sl_atr_mul=rng.uniform(1.0, 2.1),
        tp_atr_mul=rng.uniform(2.6, 6.8),
        vol_mult=rng.uniform(1.1, 2.4),
        max_daily_move_pct=rng.uniform(6.0, 12.0),
        ob_body_mult=rng.uniform(1.25, 2.15),
        cisd_len=rng.randint(3, 8),
        w_trend=rng.randint(16, 26),
        w_cisd=rng.randint(24, 40),
        w_ob=rng.randint(12, 22),
        w_fvg=rng.randint(12, 22),
        w_vol=rng.randint(8, 16),
        allow_shorts=rng.choice([True, True, True, False]),
    )


def crossover(a: Genome, b: Genome, rng: random.Random, threshold: float) -> Genome:
    vals: list[Any] = []
    for name in a.__dataclass_fields__:  # type: ignore[attr-defined]
        x = getattr(a, name)
        y = getattr(b, name)
        if isinstance(x, bool):
            vals.append(x if rng.random() < 0.5 else y)
        elif isinstance(x, int):
            rel = abs(x - y) / max(abs(x), abs(y), 1)
            vals.append(int(round((x + y) / 2)) if rel <= threshold else (x if rng.random() < 0.5 else y))
        else:
            rel = abs(x - y) / max(abs(x) + abs(y), 1e-12)
            vals.append((x + y) / 2.0 if rel <= threshold else (x if rng.random() < 0.5 else y))
    return Genome(*vals)  # type: ignore[arg-type]


def mutate(g: Genome, rng: random.Random, rate: float, strength: float) -> Genome:
    d = asdict(g)
    ranges = {
        "min_conf": (35, 80),
        "risk_pct": (0.0015, 0.01),
        "sl_atr_mul": (0.8, 2.5),
        "tp_atr_mul": (1.8, 8.0),
        "vol_mult": (0.8, 3.0),
        "max_daily_move_pct": (4.0, 16.0),
        "ob_body_mult": (1.1, 2.6),
        "cisd_len": (3, 8),
        "w_trend": (12, 30),
        "w_cisd": (20, 42),
        "w_ob": (10, 26),
        "w_fvg": (10, 26),
        "w_vol": (6, 18),
    }
    for k, v in list(d.items()):
        if rng.random() >= rate:
            continue
        if k == "allow_shorts":
            d[k] = not bool(v) if rng.random() < 0.5 else bool(v)
            continue
        lo, hi = ranges[k]
        span = hi - lo
        if isinstance(v, int):
            d[k] = int(round(clamp(v + rng.uniform(-span * strength, span * strength), lo, hi)))
        else:
            d[k] = clamp(v + rng.uniform(-span * strength, span * strength), lo, hi)
    return Genome(**d)  # type: ignore[arg-type]


def eval_genome(
    g: Genome,
    packs: MarketPacks,
    symbols: list[tuple[str, float]],
    train_ratio: float,
    fee_r: float,
) -> dict[str, object]:
    max_hold = {"15m": 96, "30m": 48, "1h": 24}
    results: list[tuple[float, float, float, float, float]] = []
    for symbol, qv in symbols:
        weight = math.sqrt(max(qv, 1.0))
        for tf in ("15m", "30m", "1h"):
            rows = packs[symbol][tf]
            candles = cast(list[Candle], rows["candles"])
            split = split_index(len(candles), train_ratio)
            train_s, fwd_s = dataset_stats(rows, g, fee_r, max_hold[tf], split)
            tb, fb = bundle(train_s), bundle(fwd_s)
            train_score, fwd_score = fitness(tb), fitness(fb)
            gap = abs(train_score - fwd_score)
            combined = (0.45 * train_score + 0.55 * fwd_score) * (
                0.8 + 0.2 * (1.0 - min(1.0, gap / 2.0))
            )
            results.append((weight, combined, train_score, fwd_score, gap))
    if not results:
        return {
            "genome": genome_dict(g),
            "fitness": -100.0,
            "train": -100.0,
            "forward": -100.0,
            "gap": 2.0,
        }
    wsum = sum(w for w, *_ in results)
    fitness_score = sum(w * c for w, c, *_ in results) / max(wsum, 1e-12)
    train_avg = sum(t for _, _, t, _, _ in results) / len(results)
    fwd_avg = sum(f for _, _, _, f, _ in results) / len(results)
    gap_avg = sum(gap for _, _, _, _, gap in results) / len(results)
    return {
        "genome": genome_dict(g),
        "fitness": fitness_score,
        "train": train_avg,
        "forward": fwd_avg,
        "gap": gap_avg,
    }


def render_report_md(settings: dict[str, Any], top3: list[dict[str, object]]) -> str:
    md = [
        "# Genetic Forward Optimization Report",
        "",
        f"- Population: {settings.get('population')}",
        f"- Generations: {settings.get('generations')}",
        f"- Elite survivors: {settings.get('elite')}",
        f"- Mutation rate: {settings.get('mutation_rate')}",
        f"- Mutation strength: {settings.get('mutation_strength')}",
        f"- Crossover threshold: {settings.get('crossover_threshold')}",
        f"- Train ratio: {settings.get('train_ratio')}",
        f"- Universe size: {settings.get('universe')}",
        f"- Lookback bars: {settings.get('lookback_bars')}",
        f"- Fee/slippage R: {settings.get('fee_r')}",
        "",
        "## Top 3",
        "",
    ]
    for i, r in enumerate(top3, 1):
        g = cast(dict[str, float | int | bool], r["genome"])
        md += [
            f"### Rank {i}",
            f"- Fitness: {float(r['fitness']):.4f}",  # type: ignore[arg-type]
            f"- Train: {float(r['train']):.4f}",  # type: ignore[arg-type]
            f"- Forward: {float(r['forward']):.4f}",  # type: ignore[arg-type]
            f"- Gap: {float(r['gap']):.4f}",  # type: ignore[arg-type]
            f"- min_conf: {g['min_conf']}",
            f"- risk_pct: {float(g['risk_pct']):.4f}",
            f"- sl_atr_mul: {float(g['sl_atr_mul']):.2f}",
            f"- tp_atr_mul: {float(g['tp_atr_mul']):.2f}",
            f"- vol_mult: {float(g['vol_mult']):.2f}",
            f"- max_daily_move_pct: {float(g['max_daily_move_pct']):.2f}",
            f"- ob_body_mult: {float(g['ob_body_mult']):.2f}",
            f"- cisd_len: {g['cisd_len']}",
            (
                f"- w_trend: {g['w_trend']}, w_cisd: {g['w_cisd']}, w_ob: {g['w_ob']}, "
                f"w_fvg: {g['w_fvg']}, w_vol: {g['w_vol']}"
            ),
            f"- allow_shorts: {g['allow_shorts']}",
            "",
        ]
    return "\n".join(md)


def run_ga_optimize(
    packs: MarketPacks,
    symbols: list[tuple[str, float]],
    *,
    population: int = 30,
    generations: int = 50,
    elite: int = 3,
    mutation_rate: float = 0.05,
    mutation_strength: float = 0.40,
    crossover_threshold: float = 0.20,
    train_ratio: float = 0.70,
    fee_r: float = 0.03,
    lookback_bars: int = 900,
    max_symbols: int = 80,
    seed: int = 42,
    on_progress: ProgressCallback | None = None,
) -> dict[str, Any]:
    """Run GA loop and return results matching ga_forward_results.json schema."""
    if not symbols:
        raise ValueError("No symbols available for GA optimize")
    rng = random.Random(seed)
    pop = [random_genome(rng) for _ in range(population)]
    best: list[dict[str, object]] = []
    for gen in range(generations):
        scored: list[tuple[float, dict[str, object]]] = []
        for genome in pop:
            res = eval_genome(genome, packs, symbols, train_ratio, fee_r)
            scored.append((float(res["fitness"]), res))  # type: ignore[arg-type]
        scored.sort(key=lambda x: x[0], reverse=True)
        best = [r for _, r in scored[:elite]]
        if on_progress:
            on_progress(
                {
                    "generation": gen + 1,
                    "generations": generations,
                    "best_fitness": scored[0][0] if scored else None,
                    "top3": [r for _, r in scored[:3]],
                    "status": "running",
                }
            )
        elites = [Genome(**r["genome"]) for r in best]  # type: ignore[arg-type]
        next_pop = elites[:]
        while len(next_pop) < population:
            a = rng.choice(elites)
            b = rng.choice(elites)
            child = crossover(a, b, rng, crossover_threshold)
            child = mutate(child, rng, mutation_rate, mutation_strength)
            next_pop.append(child)
        pop = next_pop

    final = [eval_genome(g, packs, symbols, train_ratio, fee_r) for g in pop]
    final.sort(key=lambda r: float(r["fitness"]), reverse=True)  # type: ignore[arg-type]
    top3 = final[:3]
    settings = {
        "population": population,
        "generations": generations,
        "elite": elite,
        "mutation_rate": mutation_rate,
        "mutation_strength": mutation_strength,
        "crossover_threshold": crossover_threshold,
        "train_ratio": train_ratio,
        "max_symbols": max_symbols,
        "lookback_bars": lookback_bars,
        "fee_r": fee_r,
        "universe": len(symbols),
        "seed": seed,
    }
    return {
        "settings": settings,
        "top3": top3,
        "report_md": render_report_md(settings, top3),
    }
