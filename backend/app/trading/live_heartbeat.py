"""Telegram heartbeat while a live trading session is active."""

from __future__ import annotations

import logging
from typing import Any

from backend.app.settings import Settings, get_settings
from backend.app.trading.live_session_ledger import live_session_ledger

logger = logging.getLogger("neo_fabel.trading.live_heartbeat")


def format_heartbeat_text(
    session: dict[str, Any],
    *,
    kind: str = "heartbeat",
    open_trades: int | None = None,
) -> str:
    name = session.get("session_name") or "live"
    margin = session.get("max_margin_eur")
    capital = session.get("starting_capital_eur")
    concurrent = session.get("max_concurrent_trades")
    symbols = session.get("symbol_allowlist") or []
    sizing = session.get("position_sizing") or {}
    sizing_mode = sizing.get("mode") if isinstance(sizing, dict) else None
    uptime = float(session.get("uptime_seconds") or 0)
    in_trades = float(session.get("time_in_trades_seconds") or 0)
    open_n = open_trades if open_trades is not None else session.get("last_open_trades")

    if kind == "started":
        title = "🟢 Neo live session STARTED"
    elif kind == "stopped":
        title = "⏹ Neo live session STOPPED"
    else:
        title = "❤️ Neo live heartbeat"

    lines = [
        title,
        f"session: {name}",
        f"capital/margin: €{capital} / €{margin}",
        f"max concurrent: {concurrent}",
    ]
    if symbols:
        lines.append(f"symbols: {', '.join(symbols)}")
    if sizing_mode:
        lines.append(f"sizing: {sizing_mode}")
    if kind != "started":
        lines.append(f"uptime: {int(uptime // 60)}m · in-trade: {int(in_trades // 60)}m")
    if open_n is not None:
        lines.append(f"open trades: {open_n}")
    return "\n".join(lines)


async def send_live_heartbeat(
    settings: Settings | None = None,
    *,
    kind: str = "heartbeat",
    open_trades: int | None = None,
    session_snapshot: dict[str, Any] | None = None,
) -> dict[str, Any] | None:
    """Send a Telegram heartbeat if configured; never raises to callers."""
    cfg = settings or get_settings()
    if not getattr(cfg, "live_session_telegram_heartbeat_enabled", True):
        return None
    if not cfg.telegram_enabled:
        return None

    session = session_snapshot or live_session_ledger.active
    if not session:
        return None

    text = format_heartbeat_text(session, kind=kind, open_trades=open_trades)

    try:
        from backend.app.integrations.telegram_bot import TelegramBot, TelegramNotConfigured, push_local_signal

        bot = TelegramBot(cfg)
        if not bot.configured:
            logger.debug("live heartbeat skipped — telegram not configured")
            return None
        result = await bot.send_message(text)
        push_local_signal(message=text, channel="LIVE HEARTBEAT")
        if live_session_ledger.active is not None:
            live_session_ledger.note_heartbeat(kind=kind)
        return result if isinstance(result, dict) else {"ok": True}
    except TelegramNotConfigured as exc:
        logger.debug("live heartbeat skipped: %s", exc)
        return None
    except Exception as exc:  # noqa: BLE001
        logger.warning("live heartbeat telegram send failed: %s", exc)
        return None
