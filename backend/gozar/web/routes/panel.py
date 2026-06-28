"""Remnawave panel webhook receiver — POST /panel-webhook.

Verifies an HMAC-SHA256 signature over the RAW body (constant-time) before acting. On a known
``user.expired`` / ``user.limited`` event it resets the user to claimable (committed first), then
only if they still have reminders enabled sends the matching reminder — a best-effort side-effect
fired AFTER the commit, so a failed reset never produces a misleading message.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import logging

from aiogram import Bot
from fastapi import APIRouter, Header, HTTPException, Request

from gozar.bot.replies import preview_options
from gozar.config.settings import get_settings
from gozar.db.repositories.user import UserRepository
from gozar.remnawave.schemas import PanelUser, WebhookUserEvent
from gozar.services.content import ContentService
from gozar.services.reminders import ReminderService
from gozar.services.trial import human_bytes, human_remaining

logger = logging.getLogger("gozar.web.panel")

router = APIRouter()


def _signature_ok(raw: bytes, signature: str, secret: str) -> bool:
    # VERIFY: Remnawave signs the webhook body with HMAC-SHA256 and sends the hex digest in the
    #         `x-remnawave-signature` header. Confirm the header name + scheme against the panel.
    expected = hmac.new(secret.encode(), raw, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature)


def _reminder_tokens(data: PanelUser) -> dict[str, str]:
    """The global variables an admin can drop into a reminder text — filled from the webhook's
    own user data (no extra panel call). ``{expire}`` is the time LEFT ("19h 54m"), not a date."""
    return {
        "used_traffic": human_bytes(data.traffic.used_bytes),
        "total_traffic": human_bytes(data.traffic_limit_bytes),
        "expire": human_remaining(data.expire_at),
        "remaining": human_remaining(data.expire_at),
    }


@router.post("/panel-webhook")
async def panel_webhook(
    request: Request,
    x_remnawave_signature: str = Header(default=""),
) -> dict[str, bool]:
    secret = get_settings().panel_webhook_secret.get_secret_value()
    if not secret:
        raise HTTPException(status_code=503, detail="panel webhook not configured")
    raw = await request.body()
    if not _signature_ok(raw, x_remnawave_signature, secret):
        raise HTTPException(status_code=403, detail="forbidden")
    try:
        event = WebhookUserEvent.model_validate(json.loads(raw))
    except (ValueError, TypeError):
        raise HTTPException(status_code=400, detail="bad payload") from None

    sessionmaker = request.app.state.sessionmaker
    redis = request.app.state.redis
    bot: Bot | None = getattr(request.app.state, "bot", None)

    pending: tuple[int, str, bool] | None = None
    async with sessionmaker() as session:
        outcome = await ReminderService(UserRepository(session), redis).apply_event(event)
        if outcome is not None and outcome.user.reminder_enabled:
            msg = await ContentService(session, redis).message(
                outcome.content_key, outcome.user.language, **_reminder_tokens(event.data)
            )
            pending = (outcome.user.telegram_id, msg.text, msg.link_preview)
        await session.commit()

    if pending is not None and bot is not None:  # send only AFTER the reset is durable
        try:
            await bot.send_message(
                pending[0], pending[1], link_preview_options=preview_options(pending[2])
            )
        except Exception:  # blocked user / transient — best-effort, never fail the webhook
            logger.warning("reminder send failed (ignored)")
    return {"ok": True}
