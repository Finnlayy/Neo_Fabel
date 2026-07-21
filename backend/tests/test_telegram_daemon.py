"""Telegram daemon + sentiment helpers."""

from __future__ import annotations

import time

import pytest

from backend.app.integrations import telegram_bot as bot_module
from backend.app.integrations.telegram_bot import (
    check_actionable,
    daemon_status_dict,
    parse_sentiment,
    push_local_signal,
    reset_telegram_state_for_tests,
)
from backend.app.integrations.telegram_daemon import (
    reset_telegram_daemon_for_tests,
    wake_up_daemon,
)
from backend.app.settings import Settings


@pytest.fixture(autouse=True)
def _reset_state():
    reset_telegram_state_for_tests()
    reset_telegram_daemon_for_tests()
    yield
    reset_telegram_state_for_tests()
    reset_telegram_daemon_for_tests()


def test_parse_sentiment_and_actionable():
    assert parse_sentiment("Strong buy signal on BTC") == "BULLISH"
    assert parse_sentiment("Short ETH now") == "BEARISH"
    assert parse_sentiment("Market update only") == "NEUTRAL"
    assert check_actionable("SOL breakout near resistance") is True
    assert check_actionable("Volatility index rising") is False


def test_push_local_signal_updates_daemon_counters():
    row = push_local_signal(message="Buy BTC breakout", channel="TEST")
    assert row["sentiment"] == "BULLISH"
    assert row["actionable"] is True
    status = daemon_status_dict()
    assert status["totalMessagesProcessed"] == 1
    assert len(bot_module.get_telegram_state().messages) == 1


def test_wake_up_daemon_clears_throttle():
    state = bot_module.get_telegram_state()
    state.is_throttled = True
    state.status = "THROTTLED"
    state.current_interval_ms = 1_800_000
    state.active_interval_ms = 60_000
    state._last_message_monotonic = time.monotonic() - 600

    wake_up_daemon()

    assert state.is_throttled is False
    assert state.status == "ACTIVE"
    assert state.current_interval_ms == 60_000
    assert state.wake_requested is True


@pytest.mark.asyncio
async def test_build_auto_reply_status_command():
    from backend.app.integrations.telegram_daemon import build_auto_reply

    settings = Settings(gemini_api_key="", telegram_auto_respond=True)
    bot_module.get_telegram_state().total_polls_count = 3
    bot_module.get_telegram_state().status = "ACTIVE"
    reply = await build_auto_reply(settings, "/status", "trader")
    assert "DAEMON STATUS" in reply
    assert "Polls" in reply or "Poll interval" in reply


@pytest.mark.asyncio
async def test_build_auto_reply_trade_invalid():
    from backend.app.integrations.telegram_daemon import build_auto_reply

    settings = Settings(gemini_api_key="", telegram_chat_id="999")
    reply = await build_auto_reply(settings, "/trade oops", "trader", chat_id="999")
    assert "INVALID" in reply


@pytest.mark.asyncio
async def test_build_auto_reply_trade_unauthorized_chat():
    from backend.app.integrations.telegram_daemon import build_auto_reply

    settings = Settings(gemini_api_key="", telegram_chat_id="999")
    reply = await build_auto_reply(settings, "/trade buy ada 1", "attacker", chat_id="111")
    assert "UNAUTHORIZED" in reply


@pytest.mark.asyncio
async def test_build_auto_reply_approve_unauthorized_chat():
    from backend.app.integrations.telegram_daemon import build_auto_reply

    settings = Settings(gemini_api_key="", telegram_chat_id="999")
    reply = await build_auto_reply(
        settings,
        "/approve 5diV3vz6Umj7UH7bYGBExg",
        "attacker",
        chat_id="111",
    )
    assert "UNAUTHORIZED" in reply


def test_approve_regex_accepts_token_urlsafe_ids():
    import secrets

    from backend.app.integrations.telegram_daemon import _APPROVE_RE

    pid = secrets.token_urlsafe(16)
    match = _APPROVE_RE.match(f"/approve {pid}")
    assert match is not None
    assert match.group(2) == pid
    assert _APPROVE_RE.match("/approve deadbeef") is None  # too short / old hex shape
