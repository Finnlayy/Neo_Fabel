"""Telegram bot feed routes (legacy /api/telegram paths)."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException

from ..auth import require_user
from ..integrations.telegram_bot import (
    TelegramBot,
    TelegramNotConfigured,
    daemon_status_dict,
    get_telegram_state,
    push_local_signal,
)
from ..integrations.telegram_daemon import run_daemon_poll, wake_up_daemon
from ..schemas_ai import TelegramSendRequest
from ..settings import get_settings

router = APIRouter(tags=["telegram"])


def _bot() -> TelegramBot:
    return TelegramBot(get_settings())


@router.get("/api/telegram/config")
async def telegram_config(_user: dict = Depends(require_user)) -> dict[str, str]:
    settings = get_settings()
    bot = _bot()
    username = ""
    if settings.telegram_bot_token:
        try:
            username = await bot.ensure_username()
        except Exception:  # noqa: BLE001
            username = ""
    chat_id = settings.telegram_chat_id or settings.manus_telegram_chat_id or ""
    return {
        "chatId": chat_id,
        "botUsername": username,
        "channel": settings.telegram_channel or "manus",
        "manusChatId": settings.manus_telegram_chat_id or chat_id,
        "glintChatId": settings.glint_telegram_chat_id or "",
    }


@router.get("/api/telegram/messages")
async def telegram_messages(_user: dict = Depends(require_user)) -> list[dict[str, Any]]:
    settings = get_settings()
    if not settings.telegram_enabled:
        return []
    wake_up_daemon()
    bot = _bot()
    state = get_telegram_state()
    if bot.settings.telegram_bot_token:
        try:
            await run_daemon_poll(settings)
        except TelegramNotConfigured:
            pass
        except Exception:  # noqa: BLE001 — return cached buffer on poll failure
            state.status = "THROTTLED"
    return list(state.messages)


@router.get("/api/telegram/daemon-status")
async def telegram_daemon_status(_user: dict = Depends(require_user)) -> dict[str, Any]:
    settings = get_settings()
    status = daemon_status_dict()
    if not settings.telegram_enabled or not settings.telegram_bot_token:
        status["status"] = "STOPPED"
    return status


@router.post("/api/telegram/send")
async def telegram_send(payload: TelegramSendRequest, _user: dict = Depends(require_user)) -> dict[str, Any]:
    settings = get_settings()
    if not settings.telegram_enabled:
        raise HTTPException(
            status_code=503,
            detail={"code": "telegram_disabled", "message": "TELEGRAM_ENABLED=false"},
        )
    bot = _bot()
    try:
        result = await bot.send_message(payload.message)
        ok = bool(result.get("ok")) if isinstance(result, dict) else False
        if not ok:
            raise RuntimeError(str(result))
        push_local_signal(message=payload.message, channel="FABLE 5 CONSOLE")
        wake_up_daemon()
        return {"ok": True}
    except TelegramNotConfigured as exc:
        raise HTTPException(status_code=503, detail={"code": "telegram_unconfigured", "message": str(exc)}) from exc
    except Exception as exc:
        raise HTTPException(status_code=502, detail={"code": "telegram_error", "message": str(exc)}) from exc
