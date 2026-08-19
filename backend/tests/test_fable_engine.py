"""Fable Engine P1/P2 — pure strategies, token bucket, dry-run safety."""

from __future__ import annotations

from decimal import Decimal

import pytest

from backend.app.settings import Settings
from backend.app.signals.engine.config import EngineSettings, StrategyConfig
from backend.app.signals.engine.generator import FableEngine
from backend.app.signals.engine.market_source import (
    bars_to_candles,
    ccxt_rows_to_candles,
    normalize_interval,
    resolve_source,
)
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


def test_adaptive_grid_from_candles():
    cfg = StrategyConfig(
        strategy_id="adapt",
        kind="grid",
        pair="SOLUSD",
        adaptive_range=True,
        grid_count=4,
        volume_per_zone=Decimal("0.01"),
    )
    strat = GridStrategy(cfg)
    state = StrategyState()
    # Flat-ish tape around 100 → adaptive zones; mid of lower zone triggers buy.
    history = [_candle(98 + i * 0.5) for i in range(20)]
    history.append(_candle(97.0))
    intents = strat.evaluate(history, state)
    assert state.adaptive_zones is not None
    assert len(state.adaptive_zones) == 4
    # May or may not buy depending on zone mid — at least zones resolved without error.
    assert isinstance(intents, list)


def test_paper_opportunity_pairs_scans_full_watchlist():
    from backend.app.signals.engine.generator import default_strategies, paper_opportunity_pairs

    # Max open=3 does not shrink the scan universe — capacity only gates new buys.
    settings = Settings(
        paper_max_open_positions=3,
        paper_opportunity_symbols="BTC/USD,ETH/USD,SOL/USD,XRP/USD,ADA/USD",
    )
    pairs = paper_opportunity_pairs(settings)
    assert pairs == ["BTCUSD", "ETHUSD", "SOLUSD", "XRPUSD", "ADAUSD"]
    strats = default_strategies(settings)
    assert len(strats) == 5
    assert all(s.adaptive_range for s in strats)


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
    assert state.dca_units == Decimal(0)


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


def test_engine_start_dry_run_allows_elevated_autonomy():
    """Dry-run paper loop may coexist with autonomy > 2 (live desk env)."""
    settings = Settings(
        kraken_live_trading_enabled=True,
        kraken_autonomy_level=4,
        fable_engine_enabled=True,
        fable_engine_dry_run=True,
    )
    engine = FableEngine(settings=settings, engine=EngineSettings(enabled=True, dry_run=True, strategies=[]))
    engine.assert_start_safe()


def test_engine_start_fail_closed_when_live_autonomy_not_dry_run():
    settings = Settings(
        kraken_live_trading_enabled=False,
        kraken_autonomy_level=4,
        fable_engine_enabled=True,
        fable_engine_dry_run=False,
        signal_execution_enabled=True,
    )
    engine = FableEngine(settings=settings, engine=EngineSettings(enabled=True, dry_run=False, strategies=[]))
    with pytest.raises(SignalSafetyError):
        engine.assert_start_safe()


def test_market_source_resolution_prefers_tvremix_only_with_key():
    keyed = Settings(
        tvremix_enabled=True,
        tvremix_api_key="tvr_test_key",
        fable_engine_candle_source="auto",
    )
    assert resolve_source(keyed) == "tvremix"
    unkeyed = Settings(
        tvremix_enabled=True,
        tvremix_api_key=None,
        fable_engine_candle_source="auto",
    )
    assert resolve_source(unkeyed) == "ccxt"
    forced = Settings(
        tvremix_enabled=True,
        tvremix_api_key="tvr_test_key",
        fable_engine_candle_source="ccxt",
    )
    assert resolve_source(forced) == "ccxt"
    assert resolve_source(forced, source_override="tvremix") == "tvremix"


def test_market_source_interval_mapping_month_stays_capital():
    assert normalize_interval("1D", for_ccxt=True) == "1d"
    assert normalize_interval("1W", for_ccxt=True) == "1w"
    # ccxt month is capital M — lowercasing would silently mean 1 minute.
    assert normalize_interval("1M", for_ccxt=True) == "1M"
    assert normalize_interval("garbage", for_ccxt=False) == "5m"
    assert normalize_interval("5m", for_ccxt=True) == "5m"


def test_market_source_bar_mappers_are_pure_and_exact():
    tv_raw = {
        "success": True,
        "bars": [
            {"t": 1784524500, "o": 64244.0, "h": 64388.0, "l": 64188.17, "c": 64367.99, "v": 74.89242},
            {"t": None, "c": 1.0},
            "not-a-bar",
        ],
    }
    tv = bars_to_candles(tv_raw)
    assert tv[0] == {
        "timestamp": 1784524500,
        "open": 64244.0,
        "high": 64388.0,
        "low": 64188.17,
        "close": 64367.99,
        "volume": 74.89242,
    }
    assert tv[1]["timestamp"] == 0 and tv[1]["close"] == 1.0
    assert len(tv) == 2

    ccxt_rows = [[1784524500000, 1.0, 2.0, 0.5, 1.5, 3.0], [1, 2], None]
    cc = ccxt_rows_to_candles(ccxt_rows)
    assert cc == [
        {"timestamp": 1784524500, "open": 1.0, "high": 2.0, "low": 0.5, "close": 1.5, "volume": 3.0}
    ]
    assert bars_to_candles(None) == []
    assert ccxt_rows_to_candles(None) == []


def test_dry_run_recorded_transitions_legal_and_terminal():
    from backend.app.signals.domain import LEGAL_TRANSITIONS, assert_transition

    assert_transition("approved", "dry_run_recorded")
    assert_transition("bypass_approved", "dry_run_recorded")
    assert LEGAL_TRANSITIONS["dry_run_recorded"] == frozenset()
    with pytest.raises(ValueError):
        assert_transition("dry_run_recorded", "paper_submitting")


def test_intent_signal_id_deterministic_and_bounded():
    from backend.app.signals.engine.generator import intent_signal_id
    from backend.app.signals.engine.strategies import SignalIntent

    intent = SignalIntent(
        strategy_id="s" * 64,
        kind="grid",
        pair="BTCUSD",
        side="buy",
        volume=Decimal("0.01"),
        reason="grid_buy_zone_3",
        zone=3,
        price=100.0,
    )
    first = intent_signal_id(intent, 1784524500)
    assert first == intent_signal_id(intent, 1784524500)
    assert len(first) <= 128
    assert first != intent_signal_id(intent, 1784524800)


def test_submission_view_accepts_fable_engine_source():
    from backend.app.signals.schemas import SignalSubmissionView

    view = SignalSubmissionView(
        id="e1",
        route_id="r1",
        source="fable_engine",
        signal_id="s:g:1",
        pair="BTCUSD",
        side="buy",
        volume="0.01",
        order_type="market",
        mode_snapshot="advisory",
        status="dry_run_recorded",
        reason_code="fable_dry_run",
        request_id="req",
        paper_intent_id=None,
        occurred_at="2026-07-20T12:00:00Z",
        created_at="2026-07-20T12:00:00Z",
        updated_at="2026-07-20T12:00:00Z",
    )
    assert view.source == "fable_engine"


@pytest.mark.asyncio
async def test_engine_without_session_factory_marks_memory_only():
    settings = Settings(
        kraken_live_trading_enabled=False,
        kraken_autonomy_level=2,
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
                strategy_id="g_mem",
                kind="grid",
                pair="BTCUSD",
                range_low=90.0,
                range_high=110.0,
                grid_count=2,
            )
        ],
    )

    async def fake_candles(_pair: str) -> list[dict]:
        return [
            {"timestamp": 1784524500, "open": 95.0, "high": 95.0, "low": 95.0, "close": 95.0, "volume": 1.0}
        ]

    engine = FableEngine(settings=settings, engine=engine_cfg, candle_fetcher=fake_candles)
    intents = await engine.poll_once()
    assert intents
    assert engine.dry_runs[-1]["intake"] == "memory_only"


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
