"""Background Telegram polling daemon — throttle, webhook cleanup, auto-respond."""

from __future__ import annotations

import asyncio
import logging
import re
import time
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any


from ..settings import Settings
from .gemini_client import GeminiClient
from .kraken_public import KrakenPublicClient
from .paper_factory import build_paper_router
from .telegram_bot import (
    TelegramBot,
    check_actionable,
    get_telegram_state,
    parse_sentiment,
)

logger = logging.getLogger(__name__)

_daemon_task: asyncio.Task[None] | None = None


def _authorized_telegram_chat_ids(settings: Settings) -> set[str]:
    """Operator chats allowed to run /trade, /approve, /reject, and approval callbacks."""
    ids: set[str] = set()
    for raw in (
        settings.telegram_chat_id,
        settings.manus_telegram_chat_id,
        settings.glint_telegram_chat_id,
    ):
        if raw is None:
            continue
        text = str(raw).strip()
        if text:
            ids.add(text)
    return ids


def _chat_authorized(settings: Settings, chat_id: int | str | None) -> bool:
    if chat_id is None:
        return False
    allowed = _authorized_telegram_chat_ids(settings)
    if not allowed:
        return False
    return str(chat_id).strip() in allowed
_stop_event: asyncio.Event | None = None

_TRADE_RE = re.compile(r"^/trade(?:@\w+)?\s+(\w+)\s+(\w+)\s+([\d.]+)", re.I)
# Matches secrets.token_urlsafe(16+) proposal IDs (base64url), not only hex.
_APPROVE_RE = re.compile(r"^/(approve|reject)(?:@\w+)?\s+([A-Za-z0-9_-]{16,64})\b", re.I)


def wake_up_daemon() -> None:
    """Reset idle throttle and request an immediate poll on the next loop tick."""
    state = get_telegram_state()
    state.wake_requested = True
    state._last_message_monotonic = time.monotonic()
    if state.is_throttled:
        logger.info("telegram daemon wakeup — exiting throttle")
        state.is_throttled = False
        state.status = "ACTIVE"
        state.current_interval_ms = state.active_interval_ms


def _evaluate_throttle(settings: Settings) -> None:
    state = get_telegram_state()
    now = time.monotonic()
    baseline = state._last_message_monotonic
    if baseline is None:
        baseline = now
        state._last_message_monotonic = now
    idle_sec = now - baseline
    threshold = float(settings.telegram_daemon_idle_threshold_sec)
    if idle_sec >= threshold:
        if not state.is_throttled:
            logger.info(
                "telegram daemon throttle — no messages for %.0fs (threshold %.0fs)",
                idle_sec,
                threshold,
            )
        state.is_throttled = True
        state.status = "THROTTLED"
        state.current_interval_ms = settings.telegram_daemon_throttle_ms
    else:
        state.is_throttled = False
        state.status = "ACTIVE"
        state.current_interval_ms = state.active_interval_ms
    state.time_since_last_message_sec = idle_sec


def _schedule_next_poll_time() -> None:
    state = get_telegram_state()
    nxt = datetime.now(UTC) + timedelta(milliseconds=state.current_interval_ms)
    state.next_poll_time = nxt.isoformat()


async def _fetch_market_lines(settings: Settings) -> str:
    public = KrakenPublicClient(timeout_seconds=settings.kraken_timeout_seconds)
    lines: list[str] = []
    for symbol in ("BTCUSD", "ETHUSD", "SOLUSD"):
        try:
            data = await public.ticker(symbol)
            last = data.get("last") or data.get("price") or data.get("close")
            if isinstance(last, list):
                if not last:
                    continue
                last = last[0]
            if last is None:
                continue
            price = float(last)
            label = symbol.replace("USD", "/USD")
            lines.append(f"• <b>{label}:</b> ${price:,.2f}")
        except Exception:  # noqa: BLE001
            continue
    if not lines:
        return "• <i>Market feed temporarily unavailable.</i>"
    return "\n".join(lines)


async def _paper_balance_lines(settings: Settings) -> str:
    router = build_paper_router(settings)
    status = await router.paper_status()
    raw_spot = status.get("spot")
    spot: dict[str, Any] = raw_spot if isinstance(raw_spot, dict) else {}
    raw_futures = status.get("futures")
    futures: dict[str, Any] = raw_futures if isinstance(raw_futures, dict) else {}
    spot_cash = float(spot.get("usd_balance") or status.get("usd_balance") or 0)
    fut_margin = float(futures.get("margin_balance_usd") or 0)
    open_fut = int(futures.get("open_positions") or 0)
    return (
        f"• <b>Spot cash:</b> ${spot_cash:,.2f} USD\n"
        f"• <b>Futures margin:</b> ${fut_margin:,.2f} USD\n"
        f"• <b>Open futures positions:</b> {open_fut}\n\n"
        f"<i>Source: local paper ledger ({status.get('source', 'paper')}).</i>"
    )


async def _execute_paper_trade(settings: Settings, side: str, asset: str, amount: float) -> str:
    pair = f"{asset.upper()}USD" if not asset.upper().endswith("USD") else asset.upper()
    router = build_paper_router(settings)
    result = await router.paper_order(
        side.lower(),  # type: ignore[arg-type]
        pair,
        Decimal(str(amount)),
        "market",
        None,
        market_type="spot",
    )
    order_id = result.get("order_id") or result.get("id") or f"TG-{int(time.time())}"
    return (
        "⚡ <b>FABLE 5 PAPER ORDER DISPATCH</b>\n\n"
        f"• <b>Asset:</b> {pair}\n"
        f"• <b>Direction:</b> {'🟢 BUY' if side.upper() == 'BUY' else '🔴 SELL'}\n"
        f"• <b>Amount:</b> {amount}\n"
        f"• <b>Route:</b> {result.get('source', 'local-paper-ledger')}\n\n"
        f"✅ <i>Order accepted — ID: {order_id}</i>"
    )


async def _gemini_reply(settings: Settings, text: str, from_name: str) -> str:
    client = GeminiClient(settings)
    if not client.configured:
        sentiment = parse_sentiment(text)
        return (
            "🤖 <b>FABLE 5 OS AUTO-RESPONSE</b>\n\n"
            f'Advisory accepted: <i>"{text[:240]}"</i>.\n'
            f"Sentiment: <b>{sentiment}</b>. Core systems listening."
        )
    try:
        result = await client.generate_text(
            messages=[{"role": "user", "content": text}],
            model_selection="flash",
            system=(
                "You are the Fable 5 Master Control OS assistant on Telegram. "
                "Keep replies technical, concise, under 3 short sentences. HTML allowed."
            ),
        )
        body = str(result.get("reply") or "").strip()
        return f"🤖 <b>FABLE 5 NEURAL LINK</b>\n\n{body}"
    except Exception as exc:  # noqa: BLE001
        logger.warning("telegram gemini reply failed: %s", exc)
        sentiment = parse_sentiment(text)
        return (
            "🤖 <b>FABLE 5 OS AUTO-RESPONSE</b>\n\n"
            f'Advisory accepted: <i>"{text[:240]}"</i>.\n'
            f"Sentiment: <b>{sentiment}</b>."
        )


async def build_auto_reply(
    settings: Settings,
    text: str,
    from_name: str,
    *,
    chat_id: int | str | None = None,
) -> str:
    lower = text.lower().strip()
    state = get_telegram_state()
    privileged = _chat_authorized(settings, chat_id)

    approve_match = _APPROVE_RE.match(text.strip())
    if approve_match:
        if not privileged:
            return "🚫 <b>UNAUTHORIZED</b> — approve/reject only from the configured operator chat."
        action, proposal_id = approve_match.groups()
        from backend.app.trading.trade_approvals import execute_approved_proposal, reject_proposal

        if action.lower() == "approve":
            result = await execute_approved_proposal(proposal_id, by=f"telegram:{from_name}")
            if result.get("ok"):
                return f"✅ <b>APPROVED</b> <code>{proposal_id}</code> — order dispatched."
            return f"⚠️ <b>APPROVE FAILED</b> <code>{proposal_id}</code>\n{result.get('reason') or result.get('error')}"
        result = await reject_proposal(proposal_id, by=f"telegram:{from_name}")
        if result.get("ok"):
            return f"❌ <b>REJECTED</b> <code>{proposal_id}</code>"
        return f"⚠️ <b>REJECT FAILED</b> <code>{proposal_id}</code>\n{result.get('reason')}"

    if lower.startswith("/start") or lower.startswith("/help"):
        return (
            "⚡ <b>FABLE 5 MASTER CONTROL DECK</b> ⚡\n\n"
            f"Welcome <b>@{from_name}</b>! Active command keys:\n\n"
            "🔹 <code>/status</code> — daemon telemetry\n"
            "🔹 <code>/balance</code> — paper ledger balances\n"
            "🔹 <code>/market</code> — live Kraken spot indexes\n"
            "🔹 <code>/trade buy|sell asset amount</code> — paper route\n"
            "🔹 <code>/approve id</code> / <code>/reject id</code> — live trade gate\n\n"
            "<i>Or send any prompt for Gemini neural consult.</i>"
        )
    if lower.startswith("/status"):
        status_emoji = "🟢 ACTIVE" if state.status == "ACTIVE" else "🟡 THROTTLED"
        idle = int(state.time_since_last_message_sec or 0)
        return (
            "📊 <b>FABLE 5 DAEMON STATUS</b>\n\n"
            f"• <b>State:</b> {status_emoji}\n"
            f"• <b>Poll interval:</b> {state.current_interval_ms / 1000:.0f}s\n"
            f"• <b>Polls:</b> {state.total_polls_count}\n"
            f"• <b>Messages synced:</b> {state.total_messages_processed}\n"
            f"• <b>Inactivity:</b> {idle}s\n"
            f"• <b>Next scan:</b> {state.next_poll_time or 'pending'}"
        )
    if lower.startswith("/balance"):
        body = await _paper_balance_lines(settings)
        return f"💰 <b>FABLE 5 PAPER BALANCES</b>\n\n{body}"
    if lower.startswith("/market"):
        body = await _fetch_market_lines(settings)
        return f"📈 <b>LIVE PRICE FEED</b>\n\n{body}\n\n<i>Kraken public spot indexes.</i>"
    if lower.startswith("/trade"):
        if not privileged:
            return "🚫 <b>UNAUTHORIZED</b> — paper /trade only from the configured operator chat."
        match = _TRADE_RE.match(text.strip())
        if not match:
            return (
                "⚠️ <b>INVALID ORDER FORMAT</b>\n"
                "Use: <code>/trade buy btc 0.25</code>"
            )
        order_type, asset, amount_raw = match.groups()
        amount = float(amount_raw)
        if order_type.upper() not in {"BUY", "SELL"} or amount <= 0:
            return "⚠️ <b>INVALID ORDER</b> — side must be buy/sell and amount &gt; 0."
        try:
            return await _execute_paper_trade(settings, order_type, asset, amount)
        except Exception as exc:  # noqa: BLE001
            return f"⚠️ <b>ORDER REJECTED</b>\n{exc}"
    return await _gemini_reply(settings, text, from_name)


async def _handle_incoming_message(
    bot: TelegramBot,
    settings: Settings,
    *,
    chat_id: int | str,
    text: str,
    from_name: str,
) -> None:
    state = get_telegram_state()
    state._last_message_monotonic = time.monotonic()
    if state.is_throttled:
        wake_up_daemon()

    if settings.telegram_auto_respond:
        reply = await build_auto_reply(settings, text, from_name, chat_id=chat_id)
        try:
            await bot.send_message_to(chat_id, reply, parse_mode="HTML")
        except Exception:  # noqa: BLE001
            logger.exception("telegram auto-reply failed for chat %s", chat_id)


async def run_daemon_poll(settings: Settings) -> None:
    """Single daemon poll cycle — throttle eval, getUpdates, auto-respond."""
    if not settings.telegram_enabled or not settings.telegram_bot_token:
        return

    _evaluate_throttle(settings)
    bot = TelegramBot(settings)
    state = get_telegram_state()
    state.total_polls_count += 1
    state.last_poll_time = datetime.now(UTC).isoformat()
    _schedule_next_poll_time()

    params: dict[str, Any] = {
        "timeout": 2,
        "limit": settings.telegram_poll_limit,
    }
    if state.last_update_id:
        params["offset"] = state.last_update_id + 1

    try:
        data = await bot._get("getUpdates", params=params)
    except RuntimeError as exc:
        msg = str(exc)
        if "409" in msg:
            logger.warning("telegram 409 conflict — backing off and clearing webhook")
            state.is_throttled = True
            state.status = "THROTTLED"
            state.current_interval_ms = 300_000
            try:
                await bot.delete_webhook(drop_pending=True)
            except Exception:  # noqa: BLE001
                pass
            return
        logger.warning("telegram poll failed: %s", exc)
        state.status = "THROTTLED"
        return

    results = data.get("result") if isinstance(data, dict) else None
    if not isinstance(results, list):
        return

    for update in results:
        if not isinstance(update, dict):
            continue
        update_id = int(update.get("update_id") or 0)
        if update_id > state.last_update_id:
            state.last_update_id = update_id

        callback = update.get("callback_query")
        if isinstance(callback, dict):
            await _handle_callback_query(bot, settings, callback)
            continue

        message = update.get("message")
        if not isinstance(message, dict):
            continue
        text = str(message.get("text") or message.get("caption") or "").strip()
        if not text:
            continue

        raw_from_user = message.get("from")
        from_user: dict[str, Any] = raw_from_user if isinstance(raw_from_user, dict) else {}
        if from_user.get("is_bot"):
            continue

        raw_chat = message.get("chat")
        chat: dict[str, Any] = raw_chat if isinstance(raw_chat, dict) else {}
        chat_id = chat.get("id")
        from_name = str(from_user.get("username") or from_user.get("first_name") or "User")
        channel = str(chat.get("title") or chat.get("username") or chat_id or "telegram")

        stamp = message.get("date")
        try:
            ts = datetime.fromtimestamp(int(stamp), tz=UTC) if stamp else datetime.now(UTC)
        except (TypeError, ValueError, OSError):
            ts = datetime.now(UTC)

        signal = {
            "id": f"TG-{update_id}",
            "timestamp": ts.strftime("%H:%M:%S"),
            "channel": channel.upper(),
            "message": text[:2000],
            "sentiment": parse_sentiment(text),
            "actionable": check_actionable(text),
        }
        if not any(row.get("id") == signal["id"] for row in state.messages):
            state.messages.appendleft(signal)
            state.total_messages_processed += 1
            state.last_message_received_time = ts.isoformat()

        if chat_id is not None:
            await _handle_incoming_message(
                bot,
                settings,
                chat_id=chat_id,
                text=text,
                from_name=from_name,
            )

    _evaluate_throttle(settings)


async def _handle_callback_query(bot: TelegramBot, settings: Settings, callback: dict[str, Any]) -> None:
    data = str(callback.get("data") or "")
    cq_id = str(callback.get("id") or "")
    raw_from_user = callback.get("from")
    from_user: dict[str, Any] = raw_from_user if isinstance(raw_from_user, dict) else {}
    from_name = str(from_user.get("username") or from_user.get("first_name") or "User")
    raw_message = callback.get("message")
    message: dict[str, Any] = raw_message if isinstance(raw_message, dict) else {}
    raw_chat = message.get("chat")
    chat: dict[str, Any] = raw_chat if isinstance(raw_chat, dict) else {}
    chat_id = chat.get("id")

    state = get_telegram_state()
    state._last_message_monotonic = time.monotonic()
    if state.is_throttled:
        wake_up_daemon()

    if not data.startswith("tv:"):
        if cq_id:
            await bot.answer_callback_query(cq_id, text="ignored")
        return

    if not _chat_authorized(settings, chat_id):
        if cq_id:
            await bot.answer_callback_query(cq_id, text="unauthorized chat")
        return

    parts = data.split(":")
    if len(parts) != 3:
        if cq_id:
            await bot.answer_callback_query(cq_id, text="bad callback")
        return
    _, action, proposal_id = parts
    from backend.app.trading.trade_approvals import execute_approved_proposal, reject_proposal

    if action == "ok":
        result = await execute_approved_proposal(proposal_id, by=f"telegram:{from_name}")
        note = "Approved ✅" if result.get("ok") else f"Failed: {result.get('reason') or result.get('error')}"
    elif action == "no":
        result = await reject_proposal(proposal_id, by=f"telegram:{from_name}")
        note = "Rejected ❌" if result.get("ok") else f"Failed: {result.get('reason')}"
    else:
        note = "unknown action"

    if cq_id:
        try:
            await bot.answer_callback_query(cq_id, text=note[:180])
        except Exception:  # noqa: BLE001
            pass
    if chat_id is not None:
        try:
            await bot.send_message_to(
                chat_id,
                f"🔐 Trade <code>{proposal_id}</code>: {note}",
                parse_mode="HTML",
            )
        except Exception:  # noqa: BLE001
            logger.exception("callback reply failed")



async def _daemon_loop(settings: Settings, stop_event: asyncio.Event) -> None:
    logger.info("telegram daemon loop started (interval=%sms)", settings.telegram_daemon_interval_ms)
    state = get_telegram_state()
    state.active_interval_ms = settings.telegram_daemon_interval_ms
    state.current_interval_ms = settings.telegram_daemon_interval_ms
    state.status = "ACTIVE"

    bot = TelegramBot(settings)
    try:
        await bot.delete_webhook(drop_pending=True)
        await bot.ensure_username()
    except Exception:  # noqa: BLE001
        logger.exception("telegram daemon startup cleanup failed")

    while not stop_event.is_set():
        if state.wake_requested:
            state.wake_requested = False
        try:
            await run_daemon_poll(settings)
        except Exception:  # noqa: BLE001
            logger.exception("telegram daemon poll error")

        interval_sec = max(state.current_interval_ms, 1000) / 1000.0
        if state.wake_requested:
            continue
        try:
            await asyncio.wait_for(stop_event.wait(), timeout=interval_sec)
        except TimeoutError:
            pass


async def start_telegram_daemon(settings: Settings) -> None:
    global _daemon_task, _stop_event
    if not settings.telegram_daemon_enabled:
        return
    if not settings.telegram_enabled or not settings.telegram_bot_token:
        return
    if _daemon_task is not None and not _daemon_task.done():
        return
    _stop_event = asyncio.Event()
    _daemon_task = asyncio.create_task(_daemon_loop(settings, _stop_event), name="telegram-daemon")


async def stop_telegram_daemon() -> None:
    global _daemon_task, _stop_event
    if _stop_event is not None:
        _stop_event.set()
    if _daemon_task is not None:
        _daemon_task.cancel()
        try:
            await _daemon_task
        except asyncio.CancelledError:
            pass
        _daemon_task = None
    _stop_event = None


def reset_telegram_daemon_for_tests() -> None:
    global _daemon_task, _stop_event
    _daemon_task = None
    _stop_event = None
