"""Tests for Neo Trade Agent scheduler / jobs."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from backend.app.settings import Settings
from backend.app.trading.trade_agent.runtime import TradeAgentRuntime
from backend.app.trading.trade_agent.schedules import DEFAULT_SLOTS


def test_default_slots_include_tradeagent_bats_and_et_windows():
    ids = {s.job_id for s in DEFAULT_SLOTS}
    assert "market_scan_hours" in ids
    assert "label_trades" in ids
    assert "feedback_idle" in ids
    assert "optimizer_night" in ids
    assert "et_power_hour" in ids
    assert "market_scan_morning" in ids


@pytest.mark.asyncio
async def test_runtime_start_respects_disabled_flag():
    rt = TradeAgentRuntime()
    settings = Settings(trade_agent_enabled=False)
    result = await rt.start(settings)
    assert result["started"] is False
    assert "TRADE_AGENT_ENABLED" in (result.get("reason") or "")


@pytest.mark.asyncio
async def test_runtime_trigger_market_scan_dispatches():
    rt = TradeAgentRuntime()
    with patch(
        "backend.app.trading.trade_agent.jobs.run_market_scan",
        new=AsyncMock(return_value={"ok": True, "job": "market_scan", "intent_count": 0}),
    ) as mocked:
        result = await rt.trigger("market_scan_morning", reason="test")
    assert result["ok"] is True
    mocked.assert_awaited_once()
    assert "market_scan_morning" in rt.status()["last_fired"]


@pytest.mark.asyncio
async def test_runtime_start_and_stop():
    rt = TradeAgentRuntime()
    settings = Settings(trade_agent_enabled=True, trade_agent_watchdog_enabled=False)
    started = await rt.start(settings)
    assert started["started"] is True
    assert rt.running is True
    stopped = await rt.stop()
    assert stopped["stopped"] is True
    assert rt.running is False


@pytest.mark.asyncio
async def test_label_trades_from_paper_fills(tmp_path, monkeypatch):
    from backend.app.trading.trade_agent import jobs

    async def fake_paper():
        return {
            "fills": [
                {"symbol": "ETHUSD", "side": "buy", "pnl": 12.5},
                {"symbol": "BTCUSD", "side": "sell", "pnl": -3.0},
            ]
        }

    monkeypatch.setattr(jobs, "_paper_status", fake_paper)

    original = jobs.Path

    class RootPath:
        """Stand-in so parents[3]/data/trade_agent/labels → tmp_path/labels."""

        def resolve(self):
            return self

        @property
        def parents(self):
            # parents[3] should be tmp_path so / data / trade_agent / labels works
            return (None, None, None, tmp_path)

    def path_ctor(*_a, **_k):
        return RootPath()

    monkeypatch.setattr(jobs, "Path", path_ctor)
    # Ensure Path("/something") still works if used — only __file__ path is constructed
    # jobs.py uses Path(__file__).resolve().parents[3] — our ctor ignores args.

    result = await jobs.run_label_trades(lookback_days=7)
    assert result["ok"] is True
    assert result["labeled"] == 2
    out = tmp_path / "data" / "trade_agent" / "labels"
    files = list(out.glob("labels_*.jsonl"))
    assert files, result
    text = files[0].read_text(encoding="utf-8")
    assert "win" in text and "loss" in text
    monkeypatch.setattr(jobs, "Path", original)
