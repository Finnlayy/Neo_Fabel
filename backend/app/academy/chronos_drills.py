"""Chronos Academy drills — K-line language + forecast direction (paper only)."""

from __future__ import annotations

import math
import random
from typing import Any, Literal

from backend.app.chronos.pipeline import tokenize_ohlcva
from backend.app.chronos.predictor import ChronosPredictor

Bias = Literal["bullish", "bearish", "chop"]


def _synthetic_trend_bars(n: int, bias: Bias, difficulty: int) -> list[list[float]]:
    """OHLCVA window with planted regime — no asset ID."""
    price = 100.0 + random.uniform(-5.0, 5.0)
    vol = 800.0 + 50.0 * difficulty
    drift = {"bullish": 0.0025, "bearish": -0.0025, "chop": 0.0}[bias]
    noise = 0.0015 + 0.0008 * difficulty
    if bias == "chop":
        noise *= 1.8
    bars: list[list[float]] = []
    for i in range(n):
        shock = random.gauss(drift, noise)
        # Occasional chop spike
        if bias == "chop" and random.random() < 0.15:
            shock = random.gauss(0.0, noise * 3.0)
        o = price
        c = max(price * math.exp(shock), 1e-6)
        wick = abs(c - o) * (0.2 + 0.6 * random.random())
        h = max(o, c) + wick * random.random()
        l = min(o, c) - wick * random.random()
        if h < l:
            h, l = l, h
        v = max(vol * math.exp(random.gauss(0.0, 0.05)), 1.0)
        typical = (o + h + l + c) / 4.0
        bars.append([o, h, l, c, v, v * typical])
        price = c
        vol = v
    return bars


def _direction_label(history: list[list[float]], pred_rows: list[dict[str, float]]) -> str:
    """PROCEED = bullish macro forecast; REJECT = bearish/chop."""
    if not history or not pred_rows:
        return "REJECT"
    last_close = float(history[-1][3])
    end_close = float(pred_rows[-1]["close"])
    mid_close = float(pred_rows[len(pred_rows) // 2]["close"])
    ret = (end_close / max(last_close, 1e-12)) - 1.0
    mid_ret = (mid_close / max(last_close, 1e-12)) - 1.0
    # Require consistent directional lift
    if ret > 0.004 and mid_ret > 0.0:
        return "PROCEED"
    return "REJECT"


def make_chronos_scenario(difficulty: int = 1) -> tuple[dict[str, Any], str]:
    """Build a Chronos drill scenario; returns (scenario_data, expected_outcome)."""
    difficulty = max(1, min(3, int(difficulty)))
    lookback = {1: 32, 2: 48, 3: 64}[difficulty]
    pred_len = {1: 8, 2: 12, 3: 16}[difficulty]
    bias = random.choice(["bullish", "bearish", "chop"])  # type: ignore[assignment]
    bars = _synthetic_trend_bars(lookback, bias, difficulty)

    tok = tokenize_ohlcva(bars)
    predictor = ChronosPredictor(max_context=512)
    # Slight temperature with difficulty — harder drills = noisier samples.
    temperature = 0.85 + 0.25 * difficulty
    pred = predictor.predict(
        bars,
        pred_len=pred_len,
        temperature=temperature,
        top_p=0.9,
        sample_count=3 if difficulty >= 2 else 1,
    )
    expected = _direction_label(bars, pred.pred_rows)
    # Align planted bias with label when model is ambiguous on chop/bull.
    if bias == "bullish" and expected == "REJECT" and random.random() < 0.35:
        expected = "PROCEED"
    if bias == "bearish":
        expected = "REJECT"

    s1_tail = tok.s1_ids[-8:]
    s2_tail = tok.s2_ids[-8:]
    hist_close = [float(r[3]) for r in bars]
    pred_close = [float(r["close"]) for r in pred.pred_rows]

    scenario: dict[str, Any] = {
        "mode": "chronos_kline",
        "agent": "chronos",
        "context": (
            f"Chronos K-line drill d{difficulty} (paper): read coarse/fine tokens and "
            f"forecast direction without asset IDs. Never implies live execution."
        ),
        "lookback": lookback,
        "pred_len": pred_len,
        "planted_bias": bias,
        "hint_tokens": {
            "coarse_tail": s1_tail,
            "fine_tail": s2_tail,
            "s1_unique": len(set(tok.s1_ids)),
            "s2_unique": len(set(tok.s2_ids)),
            "entropy_mean": tok.entropy_mean,
        },
        "forecast": {
            "encoder": pred.encoder,
            "last_hist_close": hist_close[-1],
            "pred_close_tail": pred_close[-min(4, len(pred_close)) :],
            "pred_return": (pred_close[-1] / max(hist_close[-1], 1e-12)) - 1.0,
            "sample_count": pred.sample_count,
            "T": pred.temperature,
        },
        # Training loop can adopt this as the Chronos "model vote".
        "model_decision": expected,
        "bars_ohlcva": bars,
    }
    return scenario, expected


def chronos_auto_decision(scenario: dict[str, Any]) -> str | None:
    """Re-run predictor on stored bars for training-loop self-play."""
    bars = scenario.get("bars_ohlcva")
    if not isinstance(bars, list) or len(bars) < 2:
        return scenario.get("model_decision")  # type: ignore[return-value]
    pred_len = int(scenario.get("pred_len") or 8)
    try:
        pred = ChronosPredictor().predict(bars, pred_len=pred_len, sample_count=1)
        return _direction_label(bars, pred.pred_rows)
    except Exception:  # noqa: BLE001
        return scenario.get("model_decision")  # type: ignore[return-value]
