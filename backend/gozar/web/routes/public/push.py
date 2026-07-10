"""Public Web Push endpoints: POST /push/subscribe + POST /push/unsubscribe.

``/subscribe`` stores (upserts) the browser's push subscription so the server can later deliver
expiry/volume nudges + broadcasts; it captures the browser's locale so a server-initiated push is
localized. ``/unsubscribe`` is the notifications-toggle-off (deactivate the row). Idempotent — it is
guarded by a Redis rate limit only, no Turnstile. The push REWARD is separate (P5 /rewards/claim).
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from gozar.db.repositories.push_subscription import PushSubscriptionRepository
from gozar.web.dependencies import DbSession
from gozar.web.routes.public.identity import CurrentDevice
from gozar.web.routes.public.security import rate_limit_ok

router = APIRouter(tags=["public"])

_SUB_LIMIT = 20
_SUB_WINDOW = 3600
_LOCALES = ("fa", "en")


class SubscribeRequest(BaseModel):
    endpoint: str = Field(min_length=1, max_length=512)
    p256dh: str = Field(min_length=1, max_length=255)
    auth: str = Field(min_length=1, max_length=255)
    locale: str = "fa"


class UnsubscribeRequest(BaseModel):
    endpoint: str = Field(min_length=1, max_length=512)


class PushResponse(BaseModel):
    ok: bool


@router.post("/push/subscribe", response_model=PushResponse)
async def subscribe(
    body: SubscribeRequest, request: Request, session: DbSession, device: CurrentDevice
) -> PushResponse:
    if not await rate_limit_ok(
        request.app.state.redis,
        "push_sub",
        device.uuid,
        limit=_SUB_LIMIT,
        window_seconds=_SUB_WINDOW,
    ):
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
    if not await rate_limit_ok(
        request.app.state.redis,
        "push_sub",
        device.uuid,
        limit=_SUB_LIMIT,
        window_seconds=_SUB_WINDOW,
    ):
        raise HTTPException(status_code=429, detail="rate_limited")
    await PushSubscriptionRepository(session).deactivate(body.endpoint)
    return PushResponse(ok=True)
