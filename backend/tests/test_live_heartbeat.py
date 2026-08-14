"""Tests for live-session Telegram heartbeat."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from backend.app.settings import Settings
from backend.app.trading.live_heartbeat import format_heartbeat_text, send_live_heartbeat
from backend.app.trading.live_session_ledger import live_session_ledger


@pytest.fixture(autouse=True)
def _reset_ledger():
    if live_session_ledger.active is not None:
        live_session_ledger.stop(status="reset")
    yield
    if live_session_ledger.active is not None:
        live_session_ledger.stop(status="reset")


def test_format_heartbeat_includes_session_caps():
    text = format_heartbeat_text(
        {
            "session_name": "20260721T0115Z_running",
            "max_margin_eur": 10,
            "starting_capital_eur": 10,
            "max_concurrent_trades": 2,
            "symbol_allowlist": ["XRPUSD", "ADAUSD"],
            "position_sizing": {"mode": "half_kelly"},
            "uptime_seconds": 3700,
            "time_in_trades_seconds": 600,
        },
        kind="heartbeat",
        open_trades=1,
    )
    assert "Neo live heartbeat" in text
    assert "XRPUSD" in text
    assert "half_kelly" in text
    assert "open trades: 1" in text


@pytest.mark.asyncio
async def test_send_heartbeat_skipped_when_disabled():
    settings = Settings(
        telegram_enabled=True,
        telegram_bot_token="x",
        telegram_chat_id="1",
        live_session_telegram_heartbeat_enabled=False,
    )
    live_session_ledger.start(
        max_margin_eur=10,
        max_concurrent_trades=2,
        autonomy=4,
        deadman_seconds=60,
    )
    assert await send_live_heartbeat(settings, kind="heartbeat") is None


@pytest.mark.asyncio
async def test_send_heartbeat_calls_telegram():
    settings = Settings(
        telegram_enabled=True,
        telegram_bot_token="token",
        telegram_chat_id="123",
        live_session_telegram_heartbeat_enabled=True,
    )
    live_session_ledger.start(
        max_margin_eur=10,
        max_concurrent_trades=2,
        symbols=["XRPUSD"],
        autonomy=4,
        deadman_seconds=60,
        position_sizing={"mode": "half_kelly"},
    )
    mock_bot = MagicMock()
    mock_bot.configured = True
    mock_bot.send_message = AsyncMock(return_value={"ok": True})
    with patch("backend.app.integrations.telegram_bot.TelegramBot", return_value=mock_bot):
        result = await send_live_heartbeat(settings, kind="started", open_trades=0)
    assert result == {"ok": True}
    mock_bot.send_message.assert_awaited_once()
    sent = mock_bot.send_message.await_args.args[0]
    assert "STARTED" in sent
    assert live_session_ledger.active["last_heartbeat_kind"] == "started"
