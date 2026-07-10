"""Web Push delivery — the site's non-Telegram notification channel (VAPID + aes128gcm, pywebpush).

Two entry points, both reused by the web (panel webhook) and the arq worker (reconcile, broadcast):
- ``send_push`` sends ONE message to ONE subscription (a single bounded attempt). pywebpush is sync
  (requests-based), so it runs off the event loop via ``asyncio.to_thread``. It returns ``GONE``
  only on a 404/410 (the endpoint is permanently dead → prune); every transient/unconfigured error
  is ``FAILED`` and the subscription is KEPT (the v1 never-mass-delete lesson).
- ``deliver_device_push`` fans a localized nudge to one device's active subscriptions: it renders
  copy from the content table in EACH subscription's own locale, sends outside any session, and
  deactivates only the ones the push service reported gone.

Logic layer only — never imports web/bot code, never logs an endpoint/key/payload (secrets).
"""

from __future__ import annotations

import asyncio
import json
import logging
from enum import StrEnum

from pywebpush import WebPushException, webpush
from redis.asyncio import Redis

from gozar.config.settings import get_settings
from gozar.db.models.enums import Language
from gozar.db.models.push_subscription import PushSubscription
from gozar.db.repositories.push_subscription import PushSubscriptionRepository
from gozar.services.content import ContentService

logger = logging.getLogger("gozar.services.push")

# HTTP statuses that mean the subscription is permanently dead → prune. Anything else is transient.
_GONE_STATUSES = {404, 410}
# ~20 sends/s — a courteous ceiling for a bulk broadcast fan-out (mirrors the bot's send throttle).
PUSH_SEND_DELAY = 0.05


class PushOutcome(StrEnum):
    SENT = "sent"
    GONE = "gone"  # 404/410 — the endpoint is permanently gone; prune it
    FAILED = "failed"  # transient error or push not configured — KEEP the subscription


def subscription_info(sub: PushSubscription) -> dict[str, object]:
    """The pywebpush ``subscription_info`` shape. Built while the row is still session-attached so
    the actual send can run after the session closes."""
    return {"endpoint": sub.endpoint, "keys": {"p256dh": sub.p256dh, "auth": sub.auth}}


def _lang(locale: str) -> Language:
    try:
        return Language(locale)
    except ValueError:
        return Language.fa


async def send_push(info: dict[str, object], payload_json: str) -> PushOutcome:
    """Send one Web Push (bounded, single attempt). ``GONE`` only on 404/410; a missing response
    (e.g. a connection error before any reply) or any other status is ``FAILED`` (kept)."""
    settings = get_settings()
    private_key = settings.vapid_private_key.get_secret_value()
    subject = settings.vapid_subject
    if not private_key or not subject:
        logger.warning("web push not configured (VAPID key/subject) — skipping send")
        return PushOutcome.FAILED

    def _blocking() -> None:
        webpush(
            subscription_info=info,
            data=payload_json,
            vapid_private_key=private_key,
            vapid_claims={"sub": subject},
            ttl=600,
        )

    try:
        await asyncio.to_thread(_blocking)
        return PushOutcome.SENT
    except WebPushException as exc:
        status = getattr(getattr(exc, "response", None), "status_code", None)
        if status in _GONE_STATUSES:
            return PushOutcome.GONE
        logger.warning("web push send failed (status=%s) — kept", status)
        return PushOutcome.FAILED
    except Exception:
        logger.warning("web push send errored — kept")
        return PushOutcome.FAILED


async def deliver_device_push(
    sessionmaker: object,
    redis: Redis,
    device_uuid: str,
    *,
    title_key: str,
    body_key: str,
    url: str,
    tokens: dict[str, str],
) -> None:
    """Localized nudge to every ACTIVE subscription of one device.

    Renders ``{title, body}`` from the content table in each subscription's own locale INSIDE a
    short session, sends OUTSIDE any session (so a slow send never holds a DB transaction), then
    prunes only the endpoints the push service reported gone. Best-effort: one failed send never
    blocks the rest and never raises to the caller.
    """
    async with sessionmaker() as session:  # type: ignore[operator]
        subs = await PushSubscriptionRepository(session).list_for_device(device_uuid)
        content = ContentService(session, redis)
        jobs: list[tuple[str, dict[str, object], str]] = []
        for sub in subs:
            lang = _lang(sub.locale)
            title = await content.text(title_key, lang, **tokens)
            body = await content.text(body_key, lang, **tokens)
            payload = json.dumps({"title": title, "body": body, "url": url})
            jobs.append((sub.endpoint, subscription_info(sub), payload))

    gone: list[str] = []
    for endpoint, info, payload in jobs:
        if await send_push(info, payload) is PushOutcome.GONE:
            gone.append(endpoint)

    if gone:
        async with sessionmaker() as session:  # type: ignore[operator]
            repo = PushSubscriptionRepository(session)
            for endpoint in gone:
                await repo.deactivate(endpoint)
            await session.commit()
