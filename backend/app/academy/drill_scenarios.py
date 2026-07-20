"""Academy drill scenario builders (fixture-backed; paper/training only).

Datei: drill_scenarios.py
Zweck: Typed scenario_data + expected_outcome for each Academy drill_type.
Erstellt: 2026-07-20 | Version: 1.0
Abhaengig: drill_market fixtures
"""

from __future__ import annotations

import random
import time
from typing import Any

from backend.app.academy.drill_market import (
    candles_to_ohlcva,
    fixture_candles,
    fixture_pack,
    fixture_quote,
    provenance,
)


def _score_exact(expected: str, actions: list[str]) -> dict[str, Any]:
    return {"mode": "exact", "acceptable": [expected], "actions": actions}


def make_market_tape_scenario(difficulty: int = 1) -> tuple[dict[str, Any], str]:
    difficulty = max(1, min(3, int(difficulty)))
    actions = ["FRESH", "STALE", "INCOMPLETE", "REJECT"]
    candles = fixture_candles(60)
    quote = fixture_quote()
    pack = fixture_pack()
    # Plant outcome by difficulty mix
    roll = random.random()
    if roll < 0.15:
        expected = "REJECT"
        age = 9999
        received = 0
        gaps = 10
    elif roll < 0.40:
        expected = "STALE"
        age = 180 + 60 * difficulty
        received = len(candles)
        gaps = 0
    elif roll < 0.60:
        expected = "INCOMPLETE"
        age = 20
        received = max(5, int(len(candles) * 0.4))
        gaps = 3 + difficulty
    else:
        expected = "FRESH"
        age = 12
        received = len(candles)
        gaps = 0

    needs_l2 = difficulty >= 2 and random.random() < 0.4
    scenario: dict[str, Any] = {
        "mode": "market_tape",
        "context": f"Judge tape freshness & completeness for BTCUSD 5m (d{difficulty}).",
        "actions": actions,
        "pair": "BTCUSD",
        "interval": "5m",
        "quote": quote,
        "candles_tail": candles[-12:],
        "freshness": {
            "last_bar_age_sec": age,
            "max_age_sec": 120,
            "gaps": gaps,
            "expected_bars": 60,
            "received_bars": received,
        },
        "levels_proxy": pack.get("levels_proxy"),
        "needs_l2": needs_l2,
        "orderbook_secondary": None,
        "data_provenance": provenance(
            primary="fixture",
            tools=["fixture_pack", "get_ohlcv", "get_quote", "analyze_smc_tool"],
            symbol_neo="BTCUSD",
            secondary_sources=["neo_kraken_public_l2"] if needs_l2 else [],
        ),
        "scoring": _score_exact(expected, actions),
    }
    return scenario, expected


def make_paper_execution_scenario(difficulty: int = 1) -> tuple[dict[str, Any], str]:
    difficulty = max(1, min(3, int(difficulty)))
    actions = ["ACCEPT_FILL", "REJECT_FILL", "REQUOTE"]
    quote = fixture_quote()
    thresholds = {"max_slippage_bps": 25, "min_fill_ratio": 0.85, "max_spread_bps": 15}
    roll = random.random()
    if roll < 0.35:
        metrics = {"slippage_bps": 4 + difficulty, "spread_bps": 2, "fill_ratio": 0.98, "latency_ms": 40}
        expected = "ACCEPT_FILL"
    elif roll < 0.65:
        metrics = {"slippage_bps": 40, "spread_bps": 8, "fill_ratio": 0.42, "latency_ms": 120}
        expected = "REJECT_FILL"
    else:
        metrics = {"slippage_bps": 8, "spread_bps": 22 + difficulty * 2, "fill_ratio": 0.95, "latency_ms": 55}
        expected = "REQUOTE"

    scenario: dict[str, Any] = {
        "mode": "paper_execution",
        "context": (
            f"Paper market buy 0.01 BTC — judge fill quality (venue=local_paper, d{difficulty})."
        ),
        "actions": actions,
        "venue": "local_paper",
        "intent": {"side": "buy", "volume": 0.01, "order_type": "market"},
        "quote": quote,
        "metrics": metrics,
        "thresholds": thresholds,
        "data_provenance": provenance(
            primary="fixture",
            tools=["fixture_pack", "get_quote", "get_ohlcv"],
            symbol_neo="BTCUSD",
        ),
        "scoring": _score_exact(expected, actions),
    }
    return scenario, expected


def make_regime_forecast_scenario(difficulty: int = 1) -> tuple[dict[str, Any], str]:
    difficulty = max(1, min(3, int(difficulty)))
    actions = ["TREND", "CHOP", "TRANSITION"]
    pack = fixture_pack()
    base_mtf = dict(pack.get("mtf") or {})
    roll = random.random()
    if roll < 0.4:
        expected = "TREND"
        mtf = {
            "alignment_score": 0.75 + 0.05 * difficulty,
            "biases": {"15m": "bullish", "1h": "bullish", "4h": "bullish"},
        }
        vol = {"atr_pct": 0.8, "regime_hint": "expanding"}
    elif roll < 0.7:
        expected = "CHOP"
        mtf = {
            "alignment_score": 0.25,
            "biases": {"15m": "neutral", "1h": "bearish", "4h": "bullish"},
        }
        vol = {"atr_pct": 1.6 + 0.2 * difficulty, "regime_hint": "contracting"}
    else:
        expected = "TRANSITION"
        mtf = {
            "alignment_score": 0.45,
            "biases": {"15m": "bullish", "1h": "neutral", "4h": "bearish"},
            "recent_flip": True,
        }
        vol = {"atr_pct": 1.2, "regime_hint": "expanding"}
    if not mtf.get("biases"):
        mtf = base_mtf

    scenario: dict[str, Any] = {
        "mode": "regime_forecast",
        "context": f"Classify multi-TF regime for BTCUSD (d{difficulty}).",
        "actions": actions,
        "mtf": mtf,
        "volatility": vol,
        "data_provenance": provenance(
            primary="fixture",
            tools=["analyze_multi_timeframe", "get_technicals", "get_ohlcv"],
            symbol_neo="BTCUSD",
        ),
        "scoring": _score_exact(expected, actions),
    }
    return scenario, expected


def make_market_brief_scenario(difficulty: int = 1) -> tuple[dict[str, Any], str]:
    difficulty = max(1, min(3, int(difficulty)))
    actions = ["BULLISH_BRIEF", "BEARISH_BRIEF", "NEUTRAL_BRIEF", "INSUFFICIENT_DATA"]
    pack = fixture_pack()
    roll = random.random()
    if roll < 0.15:
        expected = "INSUFFICIENT_DATA"
        headlines: list[dict[str, Any]] = []
        ratings: dict[str, str] = {}
    elif roll < 0.45:
        expected = "BULLISH_BRIEF"
        headlines = list(pack.get("headlines") or [])
        ratings = {"BTCUSD": "buy", "ETHUSD": "buy"}
    elif roll < 0.75:
        expected = "BEARISH_BRIEF"
        headlines = [{"title": "Risk-off flows hit crypto desks", "published": "2026-07-20T10:00:00Z"}]
        ratings = {"BTCUSD": "sell", "ETHUSD": "sell"}
    else:
        expected = "NEUTRAL_BRIEF"
        headlines = [{"title": "Markets mixed ahead of data", "published": "2026-07-20T10:00:00Z"}]
        ratings = {"BTCUSD": "neutral", "ETHUSD": "buy"}

    scenario: dict[str, Any] = {
        "mode": "market_brief",
        "context": f"Compile a paper portfolio brief from tape + headlines (d{difficulty}).",
        "actions": actions,
        "universe": ["BTCUSD", "ETHUSD"],
        "ratings": ratings,
        "headlines": headlines,
        "ledger_snapshot": {"equity": 10000, "open_positions": 0, "day_pnl_pct": 0.2 * (2 - difficulty)},
        "data_provenance": provenance(
            primary="fixture",
            tools=["get_news", "get_quotes_batch", "get_technicals_rating"],
            symbol_neo="BTCUSD",
        ),
        "scoring": _score_exact(expected, actions),
    }
    return scenario, expected


def make_param_adapt_scenario(difficulty: int = 1) -> tuple[dict[str, Any], str]:
    difficulty = max(1, min(3, int(difficulty)))
    actions = ["HOLD_PARAMS", "TIGHTEN", "LOOSEN", "VETO_TO_RISK"]
    dd_limit = 2.0
    roll = random.random()
    if roll < 0.25:
        expected = "VETO_TO_RISK"
        regime = "crisis_adjacent"
        session_dd = 1.6
    elif roll < 0.5:
        expected = "TIGHTEN"
        regime = "chop"
        session_dd = 0.8
    elif roll < 0.75:
        expected = "LOOSEN"
        regime = "trend"
        session_dd = 0.2
    else:
        expected = "HOLD_PARAMS"
        regime = "trend"
        session_dd = 0.5

    scenario: dict[str, Any] = {
        "mode": "param_adapt",
        "context": f"Retune paper risk params under risk_gov veto (d{difficulty}).",
        "actions": actions,
        "current_params": {"risk_pct": 0.5, "stop_atr_mult": 1.5},
        "regime": regime,
        "session_dd_pct": session_dd,
        "dd_limit_pct": dd_limit,
        "data_provenance": provenance(
            primary="fixture",
            tools=["analyze_multi_timeframe", "rank_symbol_setups"],
            symbol_neo="BTCUSD",
        ),
        "scoring": _score_exact(expected, actions),
    }
    return scenario, expected


def make_risk_policy_scenario(difficulty: int = 1) -> tuple[dict[str, Any], str]:
    difficulty = max(1, min(3, int(difficulty)))
    actions = ["ALLOW_PAPER", "BLOCK", "REDUCE_SIZE", "FORCE_FLAT"]
    policy = {
        "paper_only": True,
        "max_session_dd_pct": 2.0,
        "max_position_pct": 5.0,
        "pair_allowlist": ["BTCUSD", "ETHUSD"],
        "autonomy_cap": 2,
    }
    roll = random.random()
    if roll < 0.2:
        expected = "BLOCK"
        state = {
            "session_dd_pct": 0.5,
            "position_pct": 2.0,
            "requested_pair": "BTCUSD",
            "requested_autonomy": 4,
            "live_gate_requested": True,
            "open_risk_events": [],
        }
    elif roll < 0.35:
        expected = "BLOCK"
        state = {
            "session_dd_pct": 0.4,
            "position_pct": 1.0,
            "requested_pair": "SOLUSD",
            "requested_autonomy": 2,
            "live_gate_requested": False,
            "open_risk_events": [],
        }
    elif roll < 0.55:
        expected = "FORCE_FLAT"
        state = {
            "session_dd_pct": 2.1,
            "position_pct": 4.0,
            "requested_pair": "BTCUSD",
            "requested_autonomy": 2,
            "live_gate_requested": False,
            "open_risk_events": [],
        }
    elif roll < 0.75:
        expected = "REDUCE_SIZE"
        state = {
            "session_dd_pct": 1.5,
            "position_pct": 4.5,
            "requested_pair": "BTCUSD",
            "requested_autonomy": 2,
            "live_gate_requested": False,
            "open_risk_events": ["NFP_in_30m"],
        }
    else:
        expected = "ALLOW_PAPER"
        state = {
            "session_dd_pct": 0.3,
            "position_pct": 2.0,
            "requested_pair": "BTCUSD",
            "requested_autonomy": 2,
            "live_gate_requested": False,
            "open_risk_events": [],
        }

    scenario: dict[str, Any] = {
        "mode": "risk_policy",
        "context": f"Clear or block a paper trade against risk policy (d{difficulty}).",
        "actions": actions,
        "policy": policy,
        "state": state,
        "data_provenance": provenance(
            primary="fixture",
            tools=["get_economic_calendar"],
            symbol_neo=str(state["requested_pair"]),
        ),
        "scoring": _score_exact(expected, actions),
    }
    return scenario, expected


def resolve_risk_policy_expected(policy: dict[str, Any], state: dict[str, Any]) -> str:
    """Pure first-match risk decision (for tests / training auto-play)."""
    if state.get("live_gate_requested") or int(state.get("requested_autonomy") or 0) > int(
        policy.get("autonomy_cap") or 2
    ):
        return "BLOCK"
    allow = {str(p).upper() for p in (policy.get("pair_allowlist") or [])}
    if str(state.get("requested_pair") or "").upper() not in allow:
        return "BLOCK"
    dd = float(state.get("session_dd_pct") or 0.0)
    limit = float(policy.get("max_session_dd_pct") or 2.0)
    if dd >= limit:
        return "FORCE_FLAT"
    events = state.get("open_risk_events") or []
    if dd >= 0.7 * limit or events:
        return "REDUCE_SIZE"
    return "ALLOW_PAPER"


def fixture_ohlcva_for_chronos(count: int = 48) -> list[list[float]]:
    return candles_to_ohlcva(fixture_candles(count))


def now_age_freshness_stamp() -> float:
    return time.time()
