"""Website Web-Push broadcast (auth-gated) — enqueue a push to every active site subscription.

Delivery runs in the arq worker (``site_push_broadcast``), never in this request — the same fan-out
rule as the bot broadcast; a subscription is dropped only on a permanent 404/410.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from gozar.db.repositories.push_subscription import PushSubscriptionRepository
from gozar.web.dependencies import AdminUser, DbSession

router = APIRouter(prefix="/site/push", tags=["site-push"])


class PushAudienceOut(BaseModel):
    recipients: int


class PushIn(BaseModel):
    title: str = Field(min_length=1, max_length=120)
    body: str = Field(min_length=1, max_length=300)
    url: str = Field(default="", max_length=512)


class PushOut(BaseModel):
    queued: bool
    recipients: int


@router.get("/", response_model=PushAudienceOut)
async def push_audience(
    request: Request, session: DbSession, admin: AdminUser
) -> PushAudienceOut:
    return PushAudienceOut(recipients=await PushSubscriptionRepository(session).count_active())


@router.post("/", response_model=PushOut)
async def send_site_push(
    body: PushIn, request: Request, session: DbSession, admin: AdminUser
) -> PushOut:
    arq = request.app.state.arq
    if arq is None:
        raise HTTPException(503, "push worker is not configured")
    await arq.enqueue_job("site_push_broadcast", body.title, body.body, body.url)
    return PushOut(
        queued=True, recipients=await PushSubscriptionRepository(session).count_active()
    )
