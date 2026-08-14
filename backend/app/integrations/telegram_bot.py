"""Telegram Bot API helper + in-memory signal ring buffer."""

from __future__ import annotations

import re
import time
from collections import deque
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

import httpx

from ..settings import Settings

BULLISH_RE = re.compile(
    r"\b(long|buy|bull|breakout|moon|pump|up)\b|🟢",
    re.I,
)
BEARISH_RE = re.compile(
    r"\b(short|sell|bear|dump|crash|liquidation|down)\b|🔴",
    re.I,
)
ACTIONABLE_ASSETS = ("BTC", "ETH", "SOL", "MATIC", "AVAX", "XRP", "DOT", "ADA", "POL")


class TelegramNotConfigured(Exception):
    pass


@dataclass
class TelegramDaemonState:
    status: str = "STOPPED"
    current_interval_ms: int = 60_000
    active_interval_ms: int = 60_000
    last_poll_time: str | None = None
    last_message_received_time: str | None = None
    next_poll_time: str | None = None
    total_polls_count: int = 0
    total_messages_processed: int = 0
    is_throttled: bool = False
    time_since_last_message_sec: float | None = None
    bot_username: str = ""
    last_update_id: int = 0
    wake_requested: bool = False
    messages: deque[dict[str, Any]] = field(default_factory=lambda: deque(maxlen=100))
    _last_message_monotonic: float | None = None


_STATE = TelegramDaemonState()


def get_telegram_state() -> TelegramDaemonState:
    return _STATE


def reset_telegram_state_for_tests() -> None:
    global _STATE
    _STATE = TelegramDaemonState()


def parse_sentiment(text: str) -> str:
    if BULLISH_RE.search(text) and not BEARISH_RE.search(text):
        return "BULLISH"
    if BEARISH_RE.search(text) and not BULLISH_RE.search(text):
        return "BEARISH"
    return "NEUTRAL"


def check_actionable(text: str) -> bool:
    upper = text.upper()
    return any(asset in upper for asset in ACTIONABLE_ASSETS)


def push_local_signal(
    *,
    message: str,
    channel: str = "FABLE 5 CONSOLE",
    signal_id: str | None = None,
) -> dict[str, Any]:
    state = get_telegram_state()
    now = datetime.now(UTC)
    row = {
        "id": signal_id or f"TS-LOCAL-{int(now.timestamp() * 1000)}",
        "timestamp": now.strftime("%H:%M:%S"),
        "channel": channel,
        "message": message[:2000],
        "sentiment": parse_sentiment(message),
        "actionable": check_actionable(message),
    }
    state.messages.appendleft(row)
    state.last_message_received_time = now.isoformat()
    state._last_message_monotonic = time.monotonic()
    state.total_messages_processed += 1
    return row


class TelegramBot:
    def __init__(self, settings: Settings):
        self.settings = settings

    @property
    def configured(self) -> bool:
        return bool(
            self.settings.telegram_enabled
            and self.settings.telegram_bot_token
            and self.settings.telegram_chat_id
        )

    def _api_root(self) -> str:
        token = self.settings.telegram_bot_token
        if not token:
            raise TelegramNotConfigured("TELEGRAM_BOT_TOKEN is not configured")
        return f"https://api.telegram.org/bot{token}"

    async def get_me(self) -> dict[str, Any]:
        return await self._get("getMe")

    async def delete_webhook(self, *, drop_pending: bool = True) -> dict[str, Any]:
        params: dict[str, Any] = {}
        if drop_pending:
            params["drop_pending_updates"] = True
        return await self._get("deleteWebhook", params=params)

    async def send_message(
        self,
        text: str,
        *,
        parse_mode: str | None = None,
        reply_markup: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        if not self.settings.telegram_bot_token:
            raise TelegramNotConfigured("TELEGRAM_BOT_TOKEN is not configured")
        chat_id = self.settings.telegram_chat_id or self.settings.manus_telegram_chat_id
        if not chat_id:
            raise TelegramNotConfigured("TELEGRAM_CHAT_ID is not configured")
        return await self.send_message_to(
            chat_id, text, parse_mode=parse_mode, reply_markup=reply_markup
        )

    async def send_message_to(
        self,
        chat_id: int | str,
        text: str,
        *,
        parse_mode: str | None = None,
        reply_markup: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        if not self.settings.telegram_bot_token:
            raise TelegramNotConfigured("TELEGRAM_BOT_TOKEN is not configured")
        payload: dict[str, Any] = {"chat_id": chat_id, "text": text[:4000]}
        if parse_mode:
            payload["parse_mode"] = parse_mode
        if reply_markup is not None:
            payload["reply_markup"] = reply_markup
        return await self._post("sendMessage", payload)

    async def answer_callback_query(
        self,
        callback_query_id: str,
        *,
        text: str | None = None,
        show_alert: bool = False,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {"callback_query_id": callback_query_id}
        if text:
            payload["text"] = text[:200]
        if show_alert:
            payload["show_alert"] = True
        return await self._post("answerCallbackQuery", payload)

    async def poll_updates(self) -> list[dict[str, Any]]:
        """On-demand poll (used when daemon disabled)."""
        if not self.settings.telegram_bot_token:
            raise TelegramNotConfigured("TELEGRAM_BOT_TOKEN is not configured")
        from .telegram_daemon import run_daemon_poll

        await run_daemon_poll(self.settings)
        return list(get_telegram_state().messages)

    async def ensure_username(self) -> str:
        state = get_telegram_state()
        if state.bot_username:
            return state.bot_username
        me = await self.get_me()
        result = me.get("result") if isinstance(me, dict) else None
        username = ""
        if isinstance(result, dict):
            username = str(result.get("username") or "")
        state.bot_username = username
        return username

    async def _get(self, method: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        async with httpx.AsyncClient(timeout=self.settings.telegram_timeout_seconds) as client:
            response = await client.get(f"{self._api_root()}/{method}", params=params)
            if response.status_code >= 400:
                raise RuntimeError(f"Telegram HTTP {response.status_code}: {response.text[:300]}")
            return response.json()

    async def _post(self, method: str, payload: dict[str, Any]) -> dict[str, Any]:
        async with httpx.AsyncClient(timeout=self.settings.telegram_timeout_seconds) as client:
            response = await client.post(f"{self._api_root()}/{method}", json=payload)
            if response.status_code >= 400:
                raise RuntimeError(f"Telegram HTTP {response.status_code}: {response.text[:300]}")
            return response.json()


def daemon_status_dict() -> dict[str, Any]:
    state = get_telegram_state()
    running = bool(state.bot_username or state.total_polls_count or state.status != "STOPPED")
    return {
        "status": state.status if running else "STOPPED",
        "currentIntervalMs": state.current_interval_ms,
        "lastPollTime": state.last_poll_time,
        "lastMessageReceivedTime": state.last_message_received_time,
        "nextPollTime": state.next_poll_time,
        "totalPollsCount": state.total_polls_count,
        "totalMessagesProcessed": state.total_messages_processed,
        "isThrottled": state.is_throttled,
        "timeSinceLastMessageSec": state.time_since_last_message_sec,
    }
