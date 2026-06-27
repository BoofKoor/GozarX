"""Telegram webhook receiver — POST /tg/{secret}.

Verifies the secret path segment AND Telegram's ``X-Telegram-Bot-Api-Secret-Token`` header (both
constant-time) before feeding the update to the dispatcher.
"""

from __future__ import annotations

import hmac

from aiogram import Bot, Dispatcher
from aiogram.types import Update
from fastapi import APIRouter, Header, HTTPException, Request

from gozar.config.settings import Settings, get_settings

router = APIRouter()


def _webhook_authorized(secret: str, header: str, settings: Settings) -> bool:
    return hmac.compare_digest(
        secret, settings.webhook_secret.get_secret_value()
    ) and hmac.compare_digest(header, settings.webhook_header_secret.get_secret_value())


@router.post("/tg/{secret}")
async def telegram_webhook(
    secret: str,
    request: Request,
    x_telegram_bot_api_secret_token: str = Header(default=""),
) -> dict[str, bool]:
    if not _webhook_authorized(secret, x_telegram_bot_api_secret_token, get_settings()):
        raise HTTPException(status_code=403, detail="forbidden")
    bot: Bot | None = getattr(request.app.state, "bot", None)
    dp: Dispatcher | None = getattr(request.app.state, "dp", None)
    if bot is None or dp is None:
        raise HTTPException(status_code=503, detail="bot not configured")
    update = Update.model_validate(await request.json(), context={"bot": bot})
    await dp.feed_update(bot, update)
    return {"ok": True}
