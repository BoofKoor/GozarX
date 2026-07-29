"""Public Web Push endpoints: POST /push/subscribe + POST /push/unsubscribe.

``/subscribe`` stores (upserts) the browser's push subscription so the server can later deliver
expiry/volume nudges + broadcasts; it captures the browser's locale so a server-initiated push is
localized. ``/unsubscribe`` is the notifications-toggle-off (deactivate the row). Idempotent — it is
guarded by a Redis rate limit only, no Turnstile. The push REWARD is separate (P5 /rewards/claim).
"""

from __future__ import annotations

import re

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field, field_validator

from gozar.db.repositories.push_subscription import PushSubscriptionRepository
from gozar.services.push import is_allowed_push_endpoint
from gozar.web.dependencies import DbSession
from gozar.web.routes.public.identity import CurrentDevice, client_ip
from gozar.web.routes.public.security import rate_limit_ok

router = APIRouter(tags=["public"])

_SUB_LIMIT = 20
_SUB_WINDOW = 3600
# Per-IP backstop: a cookieless client is minted a fresh device uuid each request, so the per-device
# cap never bites it — the IP cap stops a cookieless flood. Generous so a CGNAT-shared IP is fine.
_SUB_IP_LIMIT = 60
_LOCALES = ("fa", "en")
_B64URL = re.compile(r"^[A-Za-z0-9_-]+=*$")


def _validate_endpoint(value: str) -> str:
    # Reject a non-https / non-push-service endpoint BEFORE storing it — the server later POSTs to
    # it, so an internal URL here would be an SSRF (the sender re-checks as defense-in-depth).
    if not is_allowed_push_endpoint(value):
        raise ValueError("invalid push endpoint")
    return value


def _validate_b64url(value: str) -> str:
    # The VAPID keys are base64url. Enforcing the encoding rejects obviously-malformed keys (a
    # fabricated "x"/"x" pair) so a bogus subscription can't be minted just to farm the push reward.
    if not _B64URL.match(value):
        raise ValueError("invalid key encoding")
    return value


class SubscribeRequest(BaseModel):
    endpoint: str = Field(min_length=1, max_length=512)
    # p256dh is a 65-byte P-256 point (~87 base64url chars); auth is 16 bytes (~22). Realistic lower
    # bounds + the base64url charset keep out placeholder/garbage keys without rejecting real ones.
    p256dh: str = Field(min_length=64, max_length=255)
    auth: str = Field(min_length=16, max_length=255)
    locale: str = "fa"

    _check_endpoint = field_validator("endpoint")(staticmethod(_validate_endpoint))
    _check_p256dh = field_validator("p256dh")(staticmethod(_validate_b64url))
    _check_auth = field_validator("auth")(staticmethod(_validate_b64url))


class UnsubscribeRequest(BaseModel):
    endpoint: str = Field(min_length=1, max_length=512)


class PushResponse(BaseModel):
    ok: bool


async def _rate_limited(request: Request, device_uuid: str) -> bool:
    """Per-device cap + a per-IP backstop (a cookieless caller mints a fresh device per request)."""
    redis = request.app.state.redis
    per_device = await rate_limit_ok(
        redis, "push_sub", device_uuid, limit=_SUB_LIMIT, window_seconds=_SUB_WINDOW
    )
    per_ip = await rate_limit_ok(
        redis, "push_sub_ip", client_ip(request), limit=_SUB_IP_LIMIT, window_seconds=_SUB_WINDOW
    )
    return not (per_device and per_ip)


@router.post("/push/subscribe", response_model=PushResponse)
async def subscribe(
    body: SubscribeRequest, request: Request, session: DbSession, device: CurrentDevice
) -> PushResponse:
    if await _rate_limited(request, device.uuid):
        raise HTTPException(status_code=429, detail="rate_limited")
    locale = body.locale if body.locale in _LOCALES else "fa"
    await PushSubscriptionRepository(session).upsert(
        device_uuid=device.uuid,
        endpoint=body.endpoint,
        p256dh=body.p256dh,
        auth=body.auth,
        locale=locale,
    )
    return PushResponse(ok=True)


@router.post("/push/unsubscribe", response_model=PushResponse)
async def unsubscribe(
    body: UnsubscribeRequest, request: Request, session: DbSession, device: CurrentDevice
) -> PushResponse:
    if await _rate_limited(request, device.uuid):
        raise HTTPException(status_code=429, detail="rate_limited")
    # Scope to THIS device — a caller must not deactivate a subscription they don't own by posting
    # someone else's endpoint URL (a leaked/shared endpoint). The prune paths stay device-agnostic.
    await PushSubscriptionRepository(session).deactivate(body.endpoint, device_uuid=device.uuid)
    return PushResponse(ok=True)
