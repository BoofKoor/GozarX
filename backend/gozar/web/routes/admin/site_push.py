"""Website Web-Push broadcast (auth-gated) — enqueue a push and record its outcome.

Delivery runs in the arq worker (``site_push_broadcast``), never in this request — the same fan-out
rule as the bot broadcast; a subscription is dropped only on a permanent 404/410.

Because the send is asynchronous the response can only ever say "queued", so every broadcast writes
a ``site_push_logs`` row here and the worker completes it. Before that the worker logged its result
to stderr and nothing else: the admin pressed send and never learned whether anything arrived.
"""

from __future__ import annotations

from datetime import datetime
from urllib.parse import urlparse

from fastapi import APIRouter, HTTPException, Query, Request
from pydantic import BaseModel, Field

from gozar.db.repositories.push_subscription import PushSubscriptionRepository
from gozar.db.repositories.site_push_log import SitePushLogRepository
from gozar.web.dependencies import AdminUser, DbSession

router = APIRouter(prefix="/site/push", tags=["site-push"])

_LOCALES = {"fa", "en"}


def _validate_url(raw: str) -> str:
    """Accept an in-site path or an absolute https URL; reject everything else.

    The value is handed to the service worker's ``notificationclick`` handler, so an unchecked
    string could send every subscriber to an arbitrary destination — including a ``javascript:``
    one — on a single mistyped or pasted value. The box was free text with no validation at all.
    """
    url = raw.strip()
    if not url:
        return ""
    if url.startswith("//"):  # protocol-relative — an off-site URL in disguise
        raise HTTPException(422, "url must be an in-site path (/status) or an https:// address")
    if url.startswith("/"):
        return url
    parsed = urlparse(url)
    if parsed.scheme == "https" and parsed.netloc:
        return url
    raise HTTPException(422, "url must be an in-site path (/status) or an https:// address")


class LocaleCount(BaseModel):
    locale: str
    count: int


class PushAudienceOut(BaseModel):
    recipients: int
    by_locale: list[LocaleCount]


class PushIn(BaseModel):
    title: str = Field(min_length=1, max_length=120)
    body: str = Field(min_length=1, max_length=300)
    url: str = Field(default="", max_length=512)
    # None (or absent) = every active subscription.
    locale: str | None = None


class PushOut(BaseModel):
    queued: bool
    recipients: int
    log_id: int


class PushLogOut(BaseModel):
    id: int
    title: str
    body: str
    url: str
    locale: str | None
    status: str
    recipients: int
    sent: int
    failed: int
    pruned: int
    created_at: datetime | None
    finished_at: datetime | None


@router.get("/", response_model=PushAudienceOut)
async def push_audience(request: Request, session: DbSession, admin: AdminUser) -> PushAudienceOut:
    """Audience size plus the per-locale split, so a targeted send shows its reach first."""
    repo = PushSubscriptionRepository(session)
    return PushAudienceOut(
        recipients=await repo.count_active(),
        by_locale=[LocaleCount(locale=loc, count=n) for loc, n in await repo.locale_breakdown()],
    )


@router.get("/history", response_model=list[PushLogOut])
async def push_history(
    request: Request,
    session: DbSession,
    admin: AdminUser,
    limit: int = Query(20, ge=1, le=100),
) -> list[PushLogOut]:
    rows = await SitePushLogRepository(session).list_recent(limit)
    return [PushLogOut.model_validate(r, from_attributes=True) for r in rows]


@router.post("/", response_model=PushOut)
async def send_site_push(
    body: PushIn, request: Request, session: DbSession, admin: AdminUser
) -> PushOut:
    arq = request.app.state.arq
    if arq is None:
        raise HTTPException(503, "push worker is not configured")
    if body.locale is not None and body.locale not in _LOCALES:
        raise HTTPException(422, "locale must be 'fa' or 'en'")

    url = _validate_url(body.url)
    subs = PushSubscriptionRepository(session)
    recipients = await subs.count_active(locale=body.locale)
    if recipients == 0:
        raise HTTPException(409, "no active subscriptions match this audience")

    # The row is written BEFORE the enqueue, so a broadcast whose job is lost still shows in the
    # history as stuck on "queued" rather than vanishing without a trace.
    log = await SitePushLogRepository(session).create(
        title=body.title, body=body.body, url=url, locale=body.locale, recipients=recipients
    )
    log_id = log.id
    await session.commit()

    await arq.enqueue_job("site_push_broadcast", body.title, body.body, url, body.locale, log_id)
    return PushOut(queued=True, recipients=recipients, log_id=log_id)
