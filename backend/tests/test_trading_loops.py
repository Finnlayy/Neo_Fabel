"""Tests for runtime paper/live loop switches."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from backend.app.settings import Settings
from backend.app.trading.loops import TradingLoopsService
from backend.app.trading.session import Level4Session, PreflightResult


@pytest.mark.asyncio
async def test_live_start_blocked_when_live_disabled():
    service = TradingLoopsService()
    settings = Settings(
        kraken_autonomy_level=4,
        kraken_live_trading_enabled=False,
    )
    session = MagicMock(spec=Level4Session)
    session._deadman_armed = False
    result = await service.start_live(settings, session)
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
    result = await service.start_live(settings, session)
    assert result["started"] is False
    assert result["reason"] == "GATES"
    assert "autonomy" in (result.get("blocked_reason") or "")


@pytest.mark.asyncio
async def test_live_start_runs_when_gates_ok():
    service = TradingLoopsService()
    settings = Settings(
        kraken_autonomy_level=4,
        kraken_live_trading_enabled=True,
        kraken_live_algo_enabled=True,
        kraken_deadman_seconds=60,
    )
    session = MagicMock(spec=Level4Session)
    session._deadman_armed = False
    session.preflight = AsyncMock(
        return_value=PreflightResult(ok=True, checks=[], autonomy_level=4, live_trading_enabled=True)
    )
    session.arm_deadman = AsyncMock(return_value={"ok": True})
    session.refresh_deadman = AsyncMock(return_value={"ok": True})
    result = await service.start_live(settings, session)
    assert result["started"] is True
    assert service.status(settings)["live"]["running"] is True
    stop = await service.stop_live()
    assert stop["stopped"] is True


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
