"""Tests for Telegram trade approval queue."""

from __future__ import annotations

from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from backend.app.trading.trade_approvals import (
    format_proposal_message,
    reject_proposal,
    trade_approvals,
)


@pytest.mark.asyncio
async def test_create_and_reject_proposal():
    proposal = trade_approvals.create(
        side="buy",
        pair="XRPUSD",
        volume=Decimal("12.5"),
        confidence_pct=72,
        rationale="breakout",
    )
    assert proposal.status == "pending"
    text = format_proposal_message(proposal)
    assert proposal.proposal_id in text
    assert "XRPUSD" in text

    result = await reject_proposal(proposal.proposal_id, by="test")
    assert result["ok"] is True
    assert result["proposal"]["status"] == "rejected"


@pytest.mark.asyncio
async def test_send_proposal_uses_inline_keyboard():
    from backend.app.settings import Settings
    from backend.app.trading.trade_approvals import send_trade_proposal_telegram

    proposal = trade_approvals.create(side="sell", pair="ADAUSD", volume="100")
    settings = Settings(telegram_enabled=True, telegram_bot_token="t", telegram_chat_id="1")
    mock_bot = MagicMock()
    mock_bot.configured = True
    mock_bot.send_message = AsyncMock(return_value={"ok": True})
    with patch("backend.app.integrations.telegram_bot.TelegramBot", return_value=mock_bot):
        await send_trade_proposal_telegram(settings, proposal)
    kwargs = mock_bot.send_message.await_args.kwargs
    assert "reply_markup" in kwargs
    assert kwargs["reply_markup"]["inline_keyboard"][0][0]["callback_data"].startswith("tv:ok:")
