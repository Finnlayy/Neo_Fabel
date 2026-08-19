"""Outbound Telegram trade-signal alerts + system online heartbeat.

Polls in the Telegram feed only ingest inbound chats. This module pushes
Signal Routes / paper outcomes (and an API-online heartbeat) to Telegram and
into the local feed ring buffer so the UI `synced` counter advances.
"""

from __future__ import annotations

import asyncio
import logging
import time
from datetime import UTC, datetime
from typing import Any

from backend.app.settings import Settings, get_settings

logger = logging.getLogger("neo_fabel.integrations.telegram_trade_notify")

_HEARTBEAT_STARTED_AT: float | None = None
_HEARTBEAT_TASK: asyncio.Task | None = None


def format_trade_signal_text(
    *,
    kind: str,
    pair: str,
    side: str,
    volume: str,
    order_type: str = "market",
    price: str | None = None,
    source: str | None = None,
    signal_id: str | None = None,
    reason_code: str | None = None,
    request_id: str | None = None,
    extra: str | None = None,
) -> str:
    titles = {
        "paper_accepted": "📈 PAPER TRADE ACCEPTED",
        "paper_failed": "⚠️ PAPER TRADE FAILED",
        "execution_unknown": "❓ PAPER EXECUTION UNKNOWN",
        "dry_run": "🧪 DRY-RUN SIGNAL",
        "shadow": "👁 SHADOW SIGNAL (exec off)",
        "mcp_fill": "📥 MCP PAPER FILL",
    }
    title = titles.get(kind, f"📡 TRADE SIGNAL ({kind})")
    lines = [
        title,
        f"• Side: {side.upper()}",
        f"• Pair: {pair}",
        f"• Volume: {volume}",
        f"• Type: {order_type}",
    ]
    if price:
        lines.append(f"• Price: {price}")
    if source:
        lines.append(f"• Source: {source}")
    if signal_id:
        lines.append(f"• Signal: {signal_id}")
    if reason_code:
        lines.append(f"• Reason: {reason_code}")
    if request_id:
        lines.append(f"• Request: {request_id}")
    if extra:
        lines.append(f"• Note: {extra}")
    return "\n".join(lines)


def format_system_heartbeat_text(
    *,
    kind: str = "heartbeat",
    uptime_seconds: float = 0,
    signal_routes_enabled: bool = False,
    signal_worker_enabled: bool = False,
    signal_execution_enabled: bool = False,
) -> str:
    if kind == "started":
        title = "🟢 Neo Fabel ONLINE"
    elif kind == "stopped":
        title = "⏹ Neo Fabel STOPPING"
    else:
        title = "❤️ Neo Fabel heartbeat"
    mins = int(max(0, uptime_seconds) // 60)
    stamp = datetime.now(UTC).strftime("%Y-%m-%d %H:%M:%SZ")
    return "\n".join(
        [
            title,
            f"time: {stamp}",
            f"uptime: {mins}m",
            f"signal routes: {'on' if signal_routes_enabled else 'off'}",
            f"signal worker: {'on' if signal_worker_enabled else 'off'}",
            f"paper exec: {'on' if signal_execution_enabled else 'off'}",
        ]
    )


async def notify_trade_signal(
    settings: Settings | None = None,
    *,
    kind: str,
    pair: str,
    side: str,
    volume: str,
    order_type: str = "market",
    price: str | None = None,
    source: str | None = None,
    signal_id: str | None = None,
    reason_code: str | None = None,
    request_id: str | None = None,
    extra: str | None = None,
    channel: str = "TRADE SIGNAL",
) -> dict[str, Any] | None:
    """Send a trade-signal Telegram message; never raises to callers."""
    cfg = settings or get_settings()
    if not getattr(cfg, "telegram_trade_signals_enabled", True):
        return None
    if not cfg.telegram_enabled:
        return None

    text = format_trade_signal_text(
        kind=kind,
        pair=pair,
        side=side,
        volume=volume,
        order_type=order_type,
        price=price,
        source=source,
        signal_id=signal_id,
        reason_code=reason_code,
        request_id=request_id,
        extra=extra,
    )
    return await _send_and_mirror(cfg, text, channel=channel)


async def send_system_heartbeat(
    settings: Settings | None = None,
    *,
    kind: str = "heartbeat",
) -> dict[str, Any] | None:
    """Send API-online heartbeat; never raises to callers."""
    cfg = settings or get_settings()
    if not getattr(cfg, "telegram_system_heartbeat_enabled", True):
        return None
    if not cfg.telegram_enabled:
        return None

    global _HEARTBEAT_STARTED_AT
    if _HEARTBEAT_STARTED_AT is None:
        _HEARTBEAT_STARTED_AT = time.monotonic()
    uptime = time.monotonic() - _HEARTBEAT_STARTED_AT
    text = format_system_heartbeat_text(
        kind=kind,
        uptime_seconds=uptime,
        signal_routes_enabled=bool(getattr(cfg, "signal_routes_enabled", False)),
        signal_worker_enabled=bool(getattr(cfg, "signal_worker_enabled", False)),
        signal_execution_enabled=bool(getattr(cfg, "signal_execution_enabled", False)),
    )
    return await _send_and_mirror(cfg, text, channel="SYSTEM HEARTBEAT")


async def _send_and_mirror(cfg: Settings, text: str, *, channel: str) -> dict[str, Any] | None:
    try:
        from backend.app.integrations.telegram_bot import (
            TelegramBot,
            TelegramNotConfigured,
            push_local_signal,
        )

        bot = TelegramBot(cfg)
        if not bot.configured:
            logger.debug("telegram notify skipped — not configured")
            return None
        result = await bot.send_message(text)
        push_local_signal(message=text, channel=channel)
        return result if isinstance(result, dict) else {"ok": True}
    except TelegramNotConfigured as exc:
        logger.debug("telegram notify skipped: %s", exc)
        return None
    except Exception as exc:  # noqa: BLE001
        logger.warning("telegram notify failed: %s", exc)
        return None


async def run_system_heartbeat_loop(settings: Settings) -> None:
    """Emit started + periodic heartbeats until cancelled."""
    global _HEARTBEAT_STARTED_AT
    _HEARTBEAT_STARTED_AT = time.monotonic()
    interval = float(getattr(settings, "telegram_system_heartbeat_seconds", 1800) or 1800)
    interval = max(60.0, interval)
    await send_system_heartbeat(settings, kind="started")
    while True:
        await asyncio.sleep(interval)
        await send_system_heartbeat(settings, kind="heartbeat")


async def start_system_heartbeat(settings: Settings) -> asyncio.Task | None:
    global _HEARTBEAT_TASK
    if not getattr(settings, "telegram_system_heartbeat_enabled", True):
        return None
    if not settings.telegram_enabled:
        return None
    if _HEARTBEAT_TASK is not None and not _HEARTBEAT_TASK.done():
        return _HEARTBEAT_TASK
    _HEARTBEAT_TASK = asyncio.create_task(
        run_system_heartbeat_loop(settings),
        name="telegram-system-heartbeat",
    )
    return _HEARTBEAT_TASK


async def stop_system_heartbeat(settings: Settings | None = None) -> None:
    global _HEARTBEAT_TASK
    cfg = settings or get_settings()
    task = _HEARTBEAT_TASK
    _HEARTBEAT_TASK = None
    if task is not None and not task.done():
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass
    try:
        await send_system_heartbeat(cfg, kind="stopped")
    except Exception:
        logger.debug("system heartbeat stop notify failed", exc_info=True)


def reset_heartbeat_state_for_tests() -> None:
    global _HEARTBEAT_STARTED_AT, _HEARTBEAT_TASK
    _HEARTBEAT_STARTED_AT = None
    _HEARTBEAT_TASK = None
