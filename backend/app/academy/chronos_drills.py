"""Chronos Academy drills — K-line language + forecast direction (paper only)."""

from __future__ import annotations

import math
import random
from typing import Any, Literal, cast

from backend.app.academy.drill_market import provenance
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
        if bias == "chop" and random.random() < 0.15:
            shock = random.gauss(0.0, noise * 3.0)
        o = price
        c = max(price * math.exp(shock), 1e-6)
        wick = abs(c - o) * (0.2 + 0.6 * random.random())
        h = max(o, c) + wick * random.random()
        low = min(o, c) - wick * random.random()
        if h < low:
            h, low = low, h
        v = max(vol * math.exp(random.gauss(0.0, 0.05)), 1.0)
        typical = (o + h + low + c) / 4.0
        bars.append([o, h, low, c, v, v * typical])
        price = c
        vol = v
    return bars


def _direction_label(
    history: list[list[float]],
    pred_rows: list[dict[str, float]],
    *,
    collapse_chop: bool = False,
    chop_eps: float = 0.004,
) -> str:
    """PROCEED / REJECT / CHOP from forecast path."""
    if not history or not pred_rows:
        return "REJECT"
    last_close = float(history[-1][3])
    end_close = float(pred_rows[-1]["close"])
    mid_close = float(pred_rows[len(pred_rows) // 2]["close"])
    ret = (end_close / max(last_close, 1e-12)) - 1.0
    mid_ret = (mid_close / max(last_close, 1e-12)) - 1.0
    if abs(ret) < chop_eps and abs(mid_ret) < chop_eps:
        return "REJECT" if collapse_chop else "CHOP"
    if ret > chop_eps and mid_ret > 0.0:
        return "PROCEED"
    if ret < -chop_eps:
        return "REJECT"
    return "REJECT" if collapse_chop else "CHOP"


def make_chronos_scenario(difficulty: int = 1) -> tuple[dict[str, Any], str]:
    """Build a Chronos drill scenario; returns (scenario_data, expected_outcome)."""
    difficulty = max(1, min(3, int(difficulty)))
    lookback = {1: 32, 2: 48, 3: 64}[difficulty]
    pred_len = {1: 8, 2: 12, 3: 16}[difficulty]
    bias = cast(Bias, random.choice(["bullish", "bearish", "chop"]))
    # Prefer synthetic bars (≥30% always); occasionally reuse fixture OHLCVA shape via market helper.
    if random.random() < 0.3:
        from backend.app.academy.drill_scenarios import fixture_ohlcva_for_chronos

        bars = fixture_ohlcva_for_chronos(lookback)
        bar_source = "fixture"
    else:
        bars = _synthetic_trend_bars(lookback, bias, difficulty)
        bar_source = "synthetic"

    collapse_chop = difficulty == 1
    actions = ["PROCEED", "REJECT"] if collapse_chop else ["PROCEED", "REJECT", "CHOP"]

    tok = tokenize_ohlcva(bars)
    predictor = ChronosPredictor(max_context=512)
    temperature = 0.85 + 0.25 * difficulty
    pred = predictor.predict(
        bars,
        pred_len=pred_len,
        temperature=temperature,
        top_p=0.9,
        sample_count=3 if difficulty >= 2 else 1,
    )
    expected = _direction_label(bars, pred.pred_rows, collapse_chop=collapse_chop)
    if bias == "bullish" and expected == "REJECT" and random.random() < 0.35:
        expected = "PROCEED"
    if bias == "bearish":
        expected = "REJECT"
    if bias == "chop" and not collapse_chop and random.random() < 0.5:
        expected = "CHOP"

    s1_tail = tok.s1_ids[-8:]
    s2_tail = tok.s2_ids[-8:]
    hist_close = [float(r[3]) for r in bars]
    pred_close = [float(r["close"]) for r in pred.pred_rows]

    scenario: dict[str, Any] = {
        "mode": "chronos_kline",
        "agent": "chronos",
        "actions": actions,
        "collapse_chop": collapse_chop,
        "bar_source": bar_source,
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
        "model_decision": expected,
        "bars_ohlcva": bars,
        "data_provenance": provenance(
            primary=bar_source,
            tools=["chronos_predictor", "fixture_pack" if bar_source == "fixture" else "synthetic"],
            symbol_neo="BTCUSD",
        ),
        "scoring": {"mode": "exact", "acceptable": [expected]},
    }
    return scenario, expected


def chronos_auto_decision(scenario: dict[str, Any]) -> str | None:
    """Re-run predictor on stored bars for training-loop self-play."""
    bars = scenario.get("bars_ohlcva")
    if not isinstance(bars, list) or len(bars) < 2:
        return scenario.get("model_decision")  # type: ignore[return-value]
    pred_len = int(scenario.get("pred_len") or 8)
    collapse = bool(scenario.get("collapse_chop"))
    try:
        pred = ChronosPredictor().predict(bars, pred_len=pred_len, sample_count=1)
        return _direction_label(bars, pred.pred_rows, collapse_chop=collapse)
    except Exception:  # noqa: BLE001
        return scenario.get("model_decision")  # type: ignore[return-value]
