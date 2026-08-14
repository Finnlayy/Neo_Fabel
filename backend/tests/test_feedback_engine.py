"""Tests for trade rationale + feedback engine."""

from __future__ import annotations

from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from backend.app.settings import Settings
from backend.app.signals.engine.strategies import SignalIntent
from backend.app.trading.feedback.engine import FeedbackEngine
from backend.app.trading.feedback.rationale import format_trade_rationale


def test_format_trade_rationale_grid_one_liner():
    intent = SignalIntent(
        strategy_id="g1",
        kind="grid",
        pair="BTCUSD",
        side="buy",
        volume=Decimal("0.001"),
        reason="grid_buy_zone_2",
        zone=2,
        price=65000.0,
        meta={"mid": 64800.0, "zone_low": 64000, "zone_high": 66000},
    )
    line = format_trade_rationale(intent)
    assert "GRID BUY BTCUSD" in line
    assert "zone 2" in line
    assert len(line) <= 180


@pytest.mark.asyncio
async def test_feedback_cycle_force_writes_notes(tmp_path, monkeypatch):
    eng = FeedbackEngine()
    settings = Settings(feedback_engine_enabled=True, kraken_live_algo_enabled=False)

    mock_engine = MagicMock()
    mock_engine.recent_dry_runs.return_value = [
        {
            "rationale": "GRID BUY ETHUSD @ 3500: zone 1 — grid_buy_zone_1",
            "intake": "memory_only",
            "reason": "grid_buy_zone_1",
        }
    ]
    mock_engine.status.return_value = {"started": True, "ticks": 30, "dry_run_count": 1, "last_error": None}
    mock_engine.engine = MagicMock(poll_seconds=10.0)
    mock_engine._strategies = []

    with (
        patch("backend.app.signals.engine.generator.get_fable_engine", return_value=mock_engine),
        patch("backend.app.trading.loops.trading_loops.status", return_value={
            "paper": {"running": True, "last_error": None},
            "live": {"running": False},
        }),
        patch("backend.app.academy.agent_registry.agent_registry.log_career_event", new=AsyncMock()),
        patch(
            "backend.app.academy.prompt_shot_optimizer.prompt_shot_optimizer.analyze_and_maybe_evolve",
            return_value={"evolved": False},
        ),
    ):
        # Redirect feedback dir
        monkeypatch.setattr(
            "backend.app.trading.feedback.engine.FEEDBACK_DIR",
            tmp_path / "feedback",
        )
        result = await eng.run_cycle(reason="test", force=True, settings=settings)

    assert result["ok"] is True
    assert result["dry_runs_reviewed"] == 1
    assert any("GRID BUY" in n or "intent:" in n for n in result["notes"])
    assert (tmp_path / "feedback").exists()


@pytest.mark.asyncio
async def test_feedback_skips_when_disabled():
    eng = FeedbackEngine()
    settings = Settings(feedback_engine_enabled=False)
    result = await eng.run_cycle(reason="test", settings=settings)
    assert result.get("skipped") is True
