"""Public contact-form endpoint: POST /contact → the ``site_messages`` inbox (read in the admin
'website' section, P9).

A contact form is a prime spam target and each submission WRITES a durable row, so — unlike the
idempotent reward endpoints — it is guarded by Turnstile (skipped when unconfigured in dev) on top
of the Redis rate limit. No identity fields are required: only a subject + message, with an OPTIONAL
free-form reply handle (email or any channel — never a Telegram handle). The sending device uuid is
stored as a plain correlation column so support can tie a message to its device without an account.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field, field_validator

from gozar.db.repositories.site_message import SiteMessageRepository
from gozar.web.dependencies import DbSession
from gozar.web.routes.public.identity import CurrentDevice, client_ip
from gozar.web.routes.public.security import rate_limit_ok, verify_turnstile

router = APIRouter(tags=["public"])

# A few messages per hour per device — enough for a genuine back-and-forth, hostile to bulk spam.
_CONTACT_LIMIT = 5
_CONTACT_WINDOW = 3600

_LOCALES = ("fa", "en")


# Stored when the user leaves the (optional) Topic select on its placeholder — keeps the inbox row's
# NOT-NULL subject sensible without forcing a choice the design marks non-required.
_DEFAULT_SUBJECT = "general"


class ContactRequest(BaseModel):
    # The message is the ONLY required field (the design hard-requires nothing else). Topic is a
    # convenience select; a free-form reply handle is optional.
    body: str = Field(min_length=1, max_length=5000)
    subject: str | None = Field(default=None, max_length=200)
    reply_handle: str | None = Field(default=None, max_length=200)
    locale: str = "fa"
    turnstile_token: str | None = None

    @field_validator("body", mode="before")
    @classmethod
    def _strip(cls, value: object) -> object:
        # Strip BEFORE the length check so a whitespace-only message fails min_length (422).
        return value.strip() if isinstance(value, str) else value


class ContactResponse(BaseModel):
    ok: bool
    reason: str | None = None


@router.post("/contact", response_model=ContactResponse)
async def submit_contact(
    body: ContactRequest, request: Request, session: DbSession, device: CurrentDevice
) -> ContactResponse:
    redis = request.app.state.redis
    if not await rate_limit_ok(
        redis, "contact", device.uuid, limit=_CONTACT_LIMIT, window_seconds=_CONTACT_WINDOW
    ):
        raise HTTPException(status_code=429, detail="rate_limited")

    http = getattr(request.app.state, "http", None)
    if not await verify_turnstile(http, body.turnstile_token or "", client_ip(request)):
        raise HTTPException(status_code=403, detail="turnstile_failed")

    subject = (body.subject or "").strip() or _DEFAULT_SUBJECT
    reply = (body.reply_handle or "").strip() or None
    locale = body.locale if body.locale in _LOCALES else "fa"
    await SiteMessageRepository(session).add(
        subject=subject,
        body=body.body,
        reply_handle=reply,
        locale=locale,
        device_uuid=device.uuid,
    )
    return ContactResponse(ok=True)
