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
from gozar.db.repositories.config_log import ConfigLogRepository
from gozar.db.repositories.site_device import SiteDeviceRepository
from gozar.db.repositories.user import UserRepository
from gozar.remnawave.schemas import PanelUser, WebhookUserEvent
from gozar.services.content import ContentService
from gozar.services.push import deliver_device_push
from gozar.services.reminders import ReminderService
from gozar.services.settings_service import SettingsService
from gozar.services.site_reminders import SiteReminderService
from gozar.services.trial import human_bytes, human_remaining

logger = logging.getLogger("gozar.web.panel")

router = APIRouter()


def _signature_ok(raw: bytes, signature: str, secret: str) -> bool:
    # Remnawave signs the RAW webhook body with HMAC-SHA256 (secret = WEBHOOK_SECRET_HEADER) and
    # sends the hex digest in `x-remnawave-signature`. The separate `x-remnawave-timestamp` header
    # is NOT part of the signed payload, so it's not mixed into the HMAC here.
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
    panel = getattr(request.app.state, "panel", None)

    pending: tuple[int, str, bool] | None = None
    async with sessionmaker() as session:
        service = ReminderService(
            UserRepository(session),
            ConfigLogRepository(session),
            SettingsService(session, redis),
            redis,
            panel,
        )
        outcome = await service.apply_event(event, _reminder_tokens(event.data))
        if outcome is not None and outcome.user.reminder_enabled:
            msg = await ContentService(session, redis).message(
                outcome.content_key, outcome.user.language, **outcome.tokens
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

    # Site path: the SAME signed webhook drives the device site too. Route by username — a site
    # panel user (``s{uuid8}_{ts}``) resolves here; a bot username never does, so ≤1 branch acts.
    # Self-heal / one-shot guard is committed BEFORE any push (durable-before-visible); push is
    # best-effort and never fails the webhook.
    site_nudge = None
    if panel is not None:
        async with sessionmaker() as session:
            site_service = SiteReminderService(
                SiteDeviceRepository(session), SettingsService(session, redis), redis, panel
            )
            site_nudge = await site_service.apply_event(event)
            await session.commit()
    if site_nudge is not None:
        try:
            await deliver_device_push(
                sessionmaker,
                redis,
                site_nudge.device_uuid,
                title_key=site_nudge.title_key,
                body_key=site_nudge.body_key,
                url="/",
                tokens=site_nudge.tokens,
            )
        except Exception:  # transient push failure — best-effort, never fail the webhook
            logger.warning("site push nudge failed (ignored)")
    return {"ok": True}
