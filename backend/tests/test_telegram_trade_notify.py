"""Tests for outbound Telegram trade signals + system heartbeat."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from backend.app.integrations.telegram_trade_notify import (
    format_system_heartbeat_text,
    format_trade_signal_text,
    notify_trade_signal,
    reset_heartbeat_state_for_tests,
    send_system_heartbeat,
)
from backend.app.settings import Settings


@pytest.fixture(autouse=True)
def _reset_hb():
    reset_heartbeat_state_for_tests()
    yield
    reset_heartbeat_state_for_tests()


def test_format_trade_signal_accepted():
    text = format_trade_signal_text(
        kind="paper_accepted",
        pair="ADAUSD",
        side="buy",
        volume="100",
        order_type="market",
        source="tradingview",
        signal_id="tv-1",
    )
    assert "PAPER TRADE ACCEPTED" in text
    assert "ADAUSD" in text
    assert "BUY" in text


def test_format_system_heartbeat():
    text = format_system_heartbeat_text(
        kind="heartbeat",
        uptime_seconds=1900,
        signal_routes_enabled=True,
        signal_worker_enabled=True,
        signal_execution_enabled=False,
    )
    assert "Neo Fabel heartbeat" in text
    assert "uptime: 31m" in text
    assert "signal routes: on" in text
    assert "paper exec: off" in text


@pytest.mark.asyncio
async def test_notify_skipped_when_trade_signals_disabled():
    settings = Settings(
        _env_file=None,
        telegram_enabled=True,
        telegram_bot_token="t",
        telegram_chat_id="1",
        telegram_trade_signals_enabled=False,
    )
    assert await notify_trade_signal(
        settings,
        kind="paper_accepted",
        pair="XRPUSD",
        side="buy",
        volume="10",
    ) is None


@pytest.mark.asyncio
async def test_notify_trade_signal_sends_and_mirrors():
    settings = Settings(
        _env_file=None,
        telegram_enabled=True,
        telegram_bot_token="token",
        telegram_chat_id="123",
        telegram_trade_signals_enabled=True,
    )
    mock_bot = MagicMock()
    mock_bot.configured = True
    mock_bot.send_message = AsyncMock(return_value={"ok": True})
    with (
        patch("backend.app.integrations.telegram_bot.TelegramBot", return_value=mock_bot),
        patch("backend.app.integrations.telegram_bot.push_local_signal") as push,
    ):
        result = await notify_trade_signal(
            settings,
            kind="paper_accepted",
            pair="ADAUSD",
            side="buy",
            volume="50",
            source="tradingview",
        )
    assert result == {"ok": True}
    mock_bot.send_message.assert_awaited_once()
    push.assert_called_once()
    assert "ADAUSD" in mock_bot.send_message.await_args.args[0]


@pytest.mark.asyncio
async def test_system_heartbeat_sends():
    settings = Settings(
        _env_file=None,
        telegram_enabled=True,
        telegram_bot_token="token",
        telegram_chat_id="123",
        telegram_system_heartbeat_enabled=True,
        signal_routes_enabled=True,
    )
    mock_bot = MagicMock()
    mock_bot.configured = True
    mock_bot.send_message = AsyncMock(return_value={"ok": True})
    with patch("backend.app.integrations.telegram_bot.TelegramBot", return_value=mock_bot):
        result = await send_system_heartbeat(settings, kind="started")
    assert result == {"ok": True}
    sent = mock_bot.send_message.await_args.args[0]
    assert "ONLINE" in sent


@pytest.mark.asyncio
async def test_system_heartbeat_skipped_when_disabled():
    settings = Settings(
        _env_file=None,
        telegram_enabled=True,
        telegram_bot_token="t",
        telegram_chat_id="1",
        telegram_system_heartbeat_enabled=False,
    )
    assert await send_system_heartbeat(settings, kind="heartbeat") is None
