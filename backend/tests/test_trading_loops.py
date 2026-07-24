"""Tests for runtime paper/live loop switches."""

from __future__ import annotations

from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock

import pytest

from backend.app.settings import Settings
from backend.app.trading.guardrails import TradingGuardrails
from backend.app.trading.live_session_ledger import live_session_ledger
from backend.app.trading.loops import TradingLoopsService
from backend.app.trading.session import Level4Session, PreflightResult


@pytest.fixture(autouse=True)
def _reset_session_ledger():
    if live_session_ledger.active is not None:
        live_session_ledger.stop(status="reset")
    yield
    if live_session_ledger.active is not None:
        live_session_ledger.stop(status="reset")


def _session_limits(**kwargs):
    return {
        "max_margin_eur": 10.0,
        "max_concurrent_trades": 2,
        "max_drawdown_usd": 2.0,
        "starting_capital_eur": 10.0,
        "symbols": ["XRPUSD", "ADAUSD"],
        "position_sizing_mode": "dynamic_kelly",
        **kwargs,
    }


@pytest.mark.asyncio
async def test_live_start_blocked_when_live_disabled():
    service = TradingLoopsService()
    settings = Settings(
        kraken_autonomy_level=4,
        kraken_live_trading_enabled=False,
    )
    session = MagicMock(spec=Level4Session)
    session._deadman_armed = False
    result = await service.start_live(settings, session, **_session_limits())
    assert result["started"] is False
    assert result["reason"] == "GATES"
    assert "KRAKEN_LIVE_TRADING_ENABLED" in (result.get("blocked_reason") or "")
    session.preflight.assert_not_called()


@pytest.mark.asyncio
async def test_live_start_blocked_when_autonomy_below_4():
    service = TradingLoopsService()
    settings = Settings(
        kraken_autonomy_level=2,
        kraken_live_trading_enabled=True,
    )
    session = MagicMock(spec=Level4Session)
    session._deadman_armed = False
    result = await service.start_live(settings, session, **_session_limits())
    assert result["started"] is False
    assert result["reason"] == "GATES"
    assert "autonomy" in (result.get("blocked_reason") or "")


@pytest.mark.asyncio
async def test_live_start_rejects_missing_margin_via_session_limits():
    service = TradingLoopsService()
    settings = Settings(
        kraken_autonomy_level=4,
        kraken_live_trading_enabled=True,
        kraken_live_algo_enabled=True,
    )
    session = MagicMock(spec=Level4Session)
    session.apply_session_limits = MagicMock(side_effect=ValueError("max_margin_eur must be > 0"))
    result = await service.start_live(
        settings,
        session,
        max_margin_eur=0,
        max_concurrent_trades=2,
        max_drawdown_usd=2,
        starting_capital_eur=10,
    )
    assert result["started"] is False
    assert result["reason"] == "SESSION_LIMITS"


@pytest.mark.asyncio
async def test_live_start_runs_when_gates_ok():
    service = TradingLoopsService()
    settings = Settings(
        kraken_autonomy_level=4,
        kraken_live_trading_enabled=True,
        kraken_live_algo_enabled=True,
        kraken_deadman_seconds=60,
        kraken_pair_allowlist="ADAUSD,XRPUSD,ADAEUR,XRPEUR",
        kraken_max_notional=Decimal("50"),
        kraken_max_open_positions=5,
    )
    session = Level4Session(settings, cli=MagicMock())
    session.cli.open_orders = AsyncMock(return_value={"open": {}})
    session.preflight = AsyncMock(
        return_value=PreflightResult(ok=True, checks=[], autonomy_level=4, live_trading_enabled=True)
    )
    session.arm_deadman = AsyncMock(return_value={"ok": True})
    session.refresh_deadman = AsyncMock(return_value={"ok": True})
    result = await service.start_live(
        settings,
        session,
        max_margin_eur=10,
        max_concurrent_trades=2,
        max_drawdown_usd=2,
        symbols=["XRPUSD", "ADAUSD"],
        starting_capital_eur=10,
        position_sizing_mode="dynamic_kelly",
    )
    assert result["started"] is True
    assert result["session"]["max_margin_eur"] == 10
    assert result["session"]["max_concurrent_trades"] == 2
    assert result["session"]["symbol_allowlist"] == ["XRPUSD", "ADAUSD"]
    assert result["session"]["position_sizing"]["mode"] == "dynamic_kelly"
    assert result["position_sizing"]["mode"] == "dynamic_kelly"
    assert result["risk_policy"]["max_drawdown_usd"] == 2
    assert set(result["guardrails"]["pair_allowlist"]) == {"XRPUSD", "ADAUSD"}
    assert result["guardrails"]["max_open_positions"] == 2
    status = service.status(settings)
    assert status["live"]["running"] is True
    assert status["live"]["session"]["symbol_allowlist"] == ["XRPUSD", "ADAUSD"]
    stop = await service.stop_live()
    assert stop["stopped"] is True
    assert stop["session"] is not None
    assert stop["session"]["status"] == "stopped"
    assert "_to_" in stop["session"]["session_name"]


@pytest.mark.asyncio
async def test_live_start_manual_sizing_requires_notional():
    service = TradingLoopsService()
    settings = Settings(
        kraken_autonomy_level=4,
        kraken_live_trading_enabled=True,
        kraken_live_algo_enabled=True,
        kraken_pair_allowlist="ADAUSD,XRPUSD",
    )
    session = Level4Session(settings, cli=MagicMock())
    result = await service.start_live(
        settings,
        session,
        max_margin_eur=10,
        max_concurrent_trades=2,
        max_drawdown_usd=2,
        starting_capital_eur=10,
        position_sizing_mode="manual",
    )
    assert result["started"] is False
    assert result["reason"] == "SESSION_LIMITS"


@pytest.mark.asyncio
async def test_live_start_manual_sizing_ok():
    service = TradingLoopsService()
    settings = Settings(
        kraken_autonomy_level=4,
        kraken_live_trading_enabled=True,
        kraken_live_algo_enabled=True,
        kraken_deadman_seconds=60,
        kraken_pair_allowlist="ADAUSD,XRPUSD",
        kraken_max_notional=Decimal("50"),
        kraken_max_open_positions=5,
    )
    session = Level4Session(settings, cli=MagicMock())
    session.cli.open_orders = AsyncMock(return_value={"open": {}})
    session.preflight = AsyncMock(
        return_value=PreflightResult(ok=True, checks=[], autonomy_level=4, live_trading_enabled=True)
    )
    session.arm_deadman = AsyncMock(return_value={"ok": True})
    session.refresh_deadman = AsyncMock(return_value={"ok": True})
    result = await service.start_live(
        settings,
        session,
        max_margin_eur=10,
        max_concurrent_trades=2,
        max_drawdown_usd=2,
        starting_capital_eur=10,
        position_sizing_mode="manual",
        manual_notional_eur=5,
    )
    assert result["started"] is True
    assert result["position_sizing"]["mode"] == "manual"
    assert result["position_sizing"]["manual_notional_eur"] == 5
    await service.stop_live()


@pytest.mark.asyncio
async def test_live_start_rejects_symbol_outside_env_allowlist():
    service = TradingLoopsService()
    settings = Settings(
        kraken_autonomy_level=4,
        kraken_live_trading_enabled=True,
        kraken_live_algo_enabled=True,
        kraken_pair_allowlist="ADAUSD,XRPUSD",
    )
    session = Level4Session(settings, cli=MagicMock())
    result = await service.start_live(
        settings,
        session,
        max_margin_eur=10,
        max_concurrent_trades=2,
        max_drawdown_usd=2,
        starting_capital_eur=10,
        symbols=["XRPUSD", "METAUSD", "ADAUSD"],
    )
    assert result["started"] is False
    assert result["reason"] == "SESSION_LIMITS"
    assert "METAUSD" in (result.get("message") or "")


def test_apply_session_limits_tightens_guardrails():
    settings = Settings(
        kraken_pair_allowlist="ADAUSD,XRPUSD,ADAEUR",
        kraken_max_notional=Decimal("50"),
        kraken_max_open_positions=5,
    )
    session = Level4Session(settings, cli=MagicMock())
    rails = session.apply_session_limits(
        max_margin_eur=10,
        max_concurrent_trades=2,
        symbols=["xrpusd", "adausd"],
    )
    assert isinstance(rails, TradingGuardrails)
    assert rails.max_notional == Decimal("10")
    assert rails.max_open_positions == 2
    assert rails.pair_allowlist == frozenset({"XRPUSD", "ADAUSD"})


def test_live_session_latches_max_drawdown_from_marked_equity():
    live_session_ledger.start(
        max_margin_eur=100,
        max_concurrent_trades=2,
        starting_capital_eur=100,
        position_sizing={"mode": "dynamic_kelly"},
        risk_policy={"max_drawdown_usd": 5},
        autonomy=4,
        deadman_seconds=60,
    )
    first = live_session_ledger.record_equity(equity_usd=100)
    assert first is not None
    assert first["max_drawdown_hit"] is False
    second = live_session_ledger.record_equity(equity_usd=96)
    assert second is not None
    assert second["session_drawdown_usd"] == 4
    hit = live_session_ledger.record_equity(equity_usd=95)
    assert hit is not None
    assert hit["max_drawdown_hit"] is True
    assert hit["status"] == "max_drawdown"


@pytest.mark.asyncio
async def test_paper_start_works_with_live_env_when_dry_run():
    """UI paper loop must start even if live trading env is on (dry-run only)."""
    from backend.app.signals.engine.generator import set_fable_engine

    set_fable_engine(None)
    service = TradingLoopsService()
    settings = Settings(
        kraken_live_trading_enabled=True,
        kraken_autonomy_level=4,
        kraken_live_algo_enabled=False,
        fable_engine_dry_run=True,
        signal_routes_enabled=False,
    )
    result = await service.start_paper(settings, session_factory=MagicMock())
    assert result["started"] is True
    assert service.status(settings)["paper"]["running"] is True
    stop = await service.stop_paper()
    assert stop["stopped"] is True


@pytest.mark.asyncio
async def test_status_reports_can_start():
    service = TradingLoopsService()
    blocked = service.status(
        Settings(kraken_autonomy_level=2, kraken_live_trading_enabled=False)
    )
    assert blocked["live"]["can_start"] is False
    ok = service.status(
        Settings(
            kraken_autonomy_level=4,
            kraken_live_trading_enabled=True,
            kraken_live_algo_enabled=True,
        )
    )
    assert ok["live"]["can_start"] is True
    supervised = service.status(
        Settings(
            kraken_autonomy_level=4,
            kraken_live_trading_enabled=True,
            kraken_live_algo_enabled=False,
        )
    )
    assert supervised["live"]["can_start"] is False
    assert "LIVE_ALGO" in (supervised["live"]["blocked_reason"] or "")
