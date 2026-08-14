"""Python twin of src/services/blindPatternScan.ts — geometry only, no prices/symbols."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

Bias = Literal["bullish", "bearish", "neutral"]
Kind = Literal["single", "double", "triple"]


@dataclass
class BlindCandle:
    dir: int  # -1 | 0 | 1
    body: float
    upper: float
    lower: float


@dataclass
class BlindPatternHit:
    name: str
    bias: Bias
    confidence: float
    kind: Kind


def _clamp01(n: float) -> float:
    return max(0.0, min(1.0, n))


def normalize_ohlc(open_: float, high: float, low: float, close: float) -> BlindCandle:
    range_ = max(high - low, 1e-12)
    body_top = max(open_, close)
    body_bot = min(open_, close)
    body = abs(close - open_) / range_
    upper = (high - body_top) / range_
    lower = (body_bot - low) / range_
    if body < 0.08:
        direction = 0
    elif close > open_:
        direction = 1
    elif close < open_:
        direction = -1
    else:
        direction = 0
    return BlindCandle(
        dir=direction,
        body=_clamp01(body),
        upper=_clamp01(upper),
        lower=_clamp01(lower),
    )


def candle_dict(c: BlindCandle) -> dict:
    return {"dir": c.dir, "body": c.body, "upper": c.upper, "lower": c.lower}


def _is_hammer(c: BlindCandle) -> bool:
    return c.lower >= 2 * max(c.body, 0.05) and c.upper <= 0.25 and c.body <= 0.4


def _is_inverted_hammer(c: BlindCandle) -> bool:
    return c.upper >= 2 * max(c.body, 0.05) and c.lower <= 0.25 and c.body <= 0.4


def _bullish_engulfing(a: BlindCandle, b: BlindCandle) -> bool:
    return a.dir < 0 and b.dir > 0 and b.body >= 0.4 and b.body >= a.body * 0.85


def _bearish_engulfing(a: BlindCandle, b: BlindCandle) -> bool:
    return a.dir > 0 and b.dir < 0 and b.body >= 0.4 and b.body >= a.body * 0.85


def _morning_star(a: BlindCandle, b: BlindCandle, c: BlindCandle) -> bool:
    return a.dir < 0 and a.body >= 0.35 and b.body <= 0.3 and c.dir > 0 and c.body >= 0.35


def _evening_star(a: BlindCandle, b: BlindCandle, c: BlindCandle) -> bool:
    return a.dir > 0 and a.body >= 0.35 and b.body <= 0.3 and c.dir < 0 and c.body >= 0.35


def scan_blind_patterns(candles: list[BlindCandle]) -> list[BlindPatternHit]:
    if not candles:
        return []
    hits: list[BlindPatternHit] = []
    n = len(candles)
    c0 = candles[n - 1]
    c1 = candles[n - 2] if n >= 2 else None
    c2 = candles[n - 3] if n >= 3 else None

    if _is_hammer(c0) and c0.dir >= 0:
        hits.append(BlindPatternHit("Hammer", "bullish", 68, "single"))
    if _is_inverted_hammer(c0) and c0.dir <= 0:
        hits.append(BlindPatternHit("Shooting Star", "bearish", 66, "single"))
    if c0.body <= 0.1:
        hits.append(BlindPatternHit("Doji", "neutral", 55, "single"))

    if c1 is not None:
        if _bullish_engulfing(c1, c0):
            hits.append(BlindPatternHit("Bullish Engulfing", "bullish", 76, "double"))
        if _bearish_engulfing(c1, c0):
            hits.append(BlindPatternHit("Bearish Engulfing", "bearish", 76, "double"))

    if c1 is not None and c2 is not None:
        if _morning_star(c2, c1, c0):
            hits.append(BlindPatternHit("Morning Star", "bullish", 80, "triple"))
        if _evening_star(c2, c1, c0):
            hits.append(BlindPatternHit("Evening Star", "bearish", 80, "triple"))

    by_name: dict[str, BlindPatternHit] = {}
    for hit in hits:
        prev = by_name.get(hit.name)
        if prev is None or hit.confidence > prev.confidence:
            by_name[hit.name] = hit
    return sorted(by_name.values(), key=lambda h: h.confidence, reverse=True)


def make_pattern_scenario(bias: Bias) -> tuple[list[dict], str]:
    """Build synthetic relative candles with a known catalog bias (no prices/symbols)."""
    if bias == "bullish":
        # Prior bearish + strong bullish engulfing
        candles = [
            BlindCandle(dir=-1, body=0.45, upper=0.1, lower=0.15),
            BlindCandle(dir=1, body=0.55, upper=0.08, lower=0.1),
        ]
        expected = "PROCEED"
    elif bias == "bearish":
        candles = [
            BlindCandle(dir=1, body=0.45, upper=0.15, lower=0.1),
            BlindCandle(dir=-1, body=0.55, upper=0.1, lower=0.08),
        ]
        expected = "REJECT"
    else:
        candles = [BlindCandle(dir=0, body=0.05, upper=0.4, lower=0.4)]
        expected = "REJECT"

    hits = scan_blind_patterns(candles)
    top = hits[0].name if hits else "unknown"
    return [candle_dict(c) for c in candles], expected if top else expected
