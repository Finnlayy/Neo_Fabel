"""Fable Engine P1/P2 — pure strategies, token bucket, dry-run safety."""

from __future__ import annotations

from decimal import Decimal

import pytest

from backend.app.settings import Settings
from backend.app.signals.engine.config import EngineSettings, StrategyConfig
from backend.app.signals.engine.generator import FableEngine
from backend.app.signals.engine.ratelimit import TokenBucket
from backend.app.signals.engine.strategies import DcaStrategy, GridStrategy, StrategyState
from backend.app.signals.safety import SignalSafetyError, assert_signals_module_imports


def _candle(close: float) -> dict:
    return {"open": close, "high": close, "low": close, "close": close, "volume": 1.0}


def test_signals_package_still_forbids_live_and_pionex_symbols():
    assert_signals_module_imports()


def test_grid_golden_intents_deterministic():
    cfg = StrategyConfig(
        strategy_id="g1",
        kind="grid",
        pair="BTCUSD",
        range_low=100.0,
        range_high=200.0,
        grid_count=4,
        volume_per_zone=Decimal("0.01"),
    )
    strat = GridStrategy(cfg)
    state = StrategyState()
    # Mid of zone 0 = 112.5 → price at 110 buys zone 0
    buys = strat.evaluate([_candle(110.0)], state)
    assert len(buys) >= 1
    assert buys[0].side == "buy"
    assert buys[0].zone == 0
    assert state.grid_inventory.get(0) == 1
    # Same price again: no second buy
    assert strat.evaluate([_candle(110.0)], state) == []
    # Rise above mid → sell
    sells = strat.evaluate([_candle(120.0)], state)
    assert any(i.side == "sell" and i.zone == 0 for i in sells)
    assert state.grid_inventory.get(0) == 0


def test_dca_drawdown_and_take_profit_golden():
    cfg = StrategyConfig(
        strategy_id="d1",
        kind="dca",
        pair="ETHUSD",
        reference_price=100.0,
        drawdown_steps_pct=[10.0, 20.0],
        dca_volume=Decimal("0.5"),
        take_profit_pct=5.0,
    )
    strat = DcaStrategy(cfg)
    state = StrategyState()
    assert strat.evaluate([_candle(95.0)], state) == []  # not yet 10%
    step0 = strat.evaluate([_candle(90.0)], state)
    assert len(step0) == 1 and step0[0].side == "buy" and step0[0].zone == 0
    step1 = strat.evaluate([_candle(80.0)], state)
    assert len(step1) == 1 and step1[0].zone == 1
    # Avg entry ~ (90*0.5 + 80*0.5)/1 = 85; TP at 85*1.05 = 89.25
    tp = strat.evaluate([_candle(90.0)], state)
    assert len(tp) == 1 and tp[0].side == "sell" and tp[0].reason == "dca_take_profit"
    assert state.dca_units == Decimal("0")


def test_token_bucket_rejects_over_budget():
    clock = {"t": 0.0}

    def now() -> float:
        return clock["t"]

    bucket = TokenBucket(rate_per_minute=2.0, now=now)
    assert bucket.allow() is True
    assert bucket.allow() is True
    assert bucket.allow() is False
    clock["t"] += 60.0
    assert bucket.allow() is True


@pytest.mark.asyncio
async def test_engine_dry_run_records_without_executor():
    settings = Settings(
        kraken_live_trading_enabled=False,
        kraken_autonomy_level=2,
        signal_execution_enabled=False,
        fable_engine_enabled=True,
        fable_engine_dry_run=True,
    )
    engine_cfg = EngineSettings(
        enabled=True,
        dry_run=True,
        poll_seconds=0.01,
        market_rpm=120.0,
        strategies=[
            StrategyConfig(
                strategy_id="g_test",
                kind="grid",
                pair="BTCUSD",
                range_low=90.0,
                range_high=110.0,
                grid_count=2,
            )
        ],
    )

    async def fake_candles(_pair: str) -> list[dict]:
        return [_candle(95.0)]

    engine = FableEngine(settings=settings, engine=engine_cfg, candle_fetcher=fake_candles)
    engine.assert_start_safe()
    intents = await engine.poll_once()
    assert intents
    assert engine.dry_runs
    assert engine.dry_runs[-1]["terminal"] == "dry_run_recorded"
    assert engine.dry_runs[-1]["pair"] == "BTCUSD"


def test_engine_start_fail_closed_when_live_autonomy():
    settings = Settings(
        kraken_live_trading_enabled=False,
        kraken_autonomy_level=4,
        fable_engine_enabled=True,
        fable_engine_dry_run=True,
    )
    engine = FableEngine(settings=settings, engine=EngineSettings(enabled=True, dry_run=True, strategies=[]))
    with pytest.raises(SignalSafetyError):
        engine.assert_start_safe()


def test_engine_start_fail_closed_inconsistent_dry_run_false():
    settings = Settings(
        kraken_live_trading_enabled=False,
        kraken_autonomy_level=2,
        signal_execution_enabled=False,
        fable_engine_enabled=True,
        fable_engine_dry_run=False,
    )
    engine = FableEngine(
        settings=settings,
        engine=EngineSettings(enabled=True, dry_run=False, strategies=[]),
    )
    with pytest.raises(SignalSafetyError, match="DRY_RUN=false"):
        engine.assert_start_safe()
