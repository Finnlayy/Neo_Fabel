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


BULLISH_RE = re.compile(r"\b(long|buy|bull|breakout|moon|pump)\b", re.I)
BEARISH_RE = re.compile(r"\b(short|sell|bear|dump|crash|liquidation)\b", re.I)


class TelegramNotConfigured(Exception):
    pass


@dataclass
class TelegramDaemonState:
    status: str = "STOPPED"
    current_interval_ms: int = 5000
    last_poll_time: str | None = None
    last_message_received_time: str | None = None
    next_poll_time: str | None = None
    total_polls_count: int = 0
    total_messages_processed: int = 0
    is_throttled: bool = False
    time_since_last_message_sec: float | None = None
    bot_username: str = ""
    last_update_id: int = 0
    messages: deque[dict[str, Any]] = field(default_factory=lambda: deque(maxlen=100))
    _last_message_monotonic: float | None = None


_STATE = TelegramDaemonState()


def get_telegram_state() -> TelegramDaemonState:
    return _STATE


def reset_telegram_state_for_tests() -> None:
    global _STATE
    _STATE = TelegramDaemonState()


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

    async def send_message(self, text: str) -> dict[str, Any]:
        if not self.configured:
            raise TelegramNotConfigured("Telegram bot token/chat id not configured")
        chat_id = self.settings.telegram_chat_id
        assert chat_id
        return await self._post(
            "sendMessage",
            {"chat_id": chat_id, "text": text[:4000]},
        )

    async def poll_updates(self) -> list[dict[str, Any]]:
        if not self.settings.telegram_bot_token:
            raise TelegramNotConfigured("TELEGRAM_BOT_TOKEN is not configured")
        state = get_telegram_state()
        params: dict[str, Any] = {
            "timeout": 0,
            "limit": self.settings.telegram_poll_limit,
        }
        if state.last_update_id:
            params["offset"] = state.last_update_id + 1
        data = await self._get("getUpdates", params=params)
        state.total_polls_count += 1
        state.last_poll_time = datetime.now(UTC).isoformat()
        state.next_poll_time = state.last_poll_time
        state.status = "ACTIVE"
        results = data.get("result") if isinstance(data, dict) else None
        if not isinstance(results, list):
            return []
        mapped: list[dict[str, Any]] = []
        for update in results:
            if not isinstance(update, dict):
                continue
            update_id = int(update.get("update_id") or 0)
            if update_id > state.last_update_id:
                state.last_update_id = update_id
            signal = _map_update(update)
            if signal is None:
                continue
            state.messages.appendleft(signal)
            state.total_messages_processed += 1
            state.last_message_received_time = signal["timestamp"]
            state._last_message_monotonic = time.monotonic()
            mapped.append(signal)
        if state._last_message_monotonic is not None:
            state.time_since_last_message_sec = time.monotonic() - state._last_message_monotonic
        return mapped

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


def _map_update(update: dict[str, Any]) -> dict[str, Any] | None:
    message = update.get("message") or update.get("channel_post")
    if not isinstance(message, dict):
        return None
    text = str(message.get("text") or message.get("caption") or "").strip()
    if not text:
        return None
    raw_chat = message.get("chat")
    chat: dict[str, Any] = raw_chat if isinstance(raw_chat, dict) else {}
    channel = str(chat.get("title") or chat.get("username") or chat.get("id") or "telegram")
    sentiment = "NEUTRAL"
    if BULLISH_RE.search(text) and not BEARISH_RE.search(text):
        sentiment = "BULLISH"
    elif BEARISH_RE.search(text) and not BULLISH_RE.search(text):
        sentiment = "BEARISH"
    stamp = message.get("date")
    try:
        if not isinstance(stamp, (str, int, float)):
            raise TypeError("Telegram date is not numeric")
        ts = datetime.fromtimestamp(int(stamp), tz=UTC).isoformat()
    except (TypeError, ValueError, OSError):
        ts = datetime.now(UTC).isoformat()
    return {
        "id": f"TG-{update.get('update_id')}",
        "timestamp": ts,
        "channel": channel,
        "message": text[:2000],
        "sentiment": sentiment,
        "actionable": sentiment != "NEUTRAL",
    }


def daemon_status_dict() -> dict[str, Any]:
    state = get_telegram_state()
    return {
        "status": state.status if state.bot_username or state.total_polls_count else "STOPPED",
        "currentIntervalMs": state.current_interval_ms,
        "lastPollTime": state.last_poll_time,
        "lastMessageReceivedTime": state.last_message_received_time,
        "nextPollTime": state.next_poll_time,
        "totalPollsCount": state.total_polls_count,
        "totalMessagesProcessed": state.total_messages_processed,
        "isThrottled": state.is_throttled,
        "timeSinceLastMessageSec": state.time_since_last_message_sec,
    }
