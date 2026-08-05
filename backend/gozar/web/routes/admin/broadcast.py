"""Admin broadcast (auth-gated) — compose a message, choose who gets it, and send it.

The bot's ``/admin`` copies/forwards a Telegram message; the web panel has no source message, so it
composes text and enqueues the ``broadcast_text`` worker job (same "never drop a user on a transient
error" allowlist as the bot fan-out). Live progress is reported to the first configured owner in
Telegram; delivery happens in the worker, never in this request.

Everything the composer offers is enforced HERE as well as shown there:

- the audience is language groups plus two refinements (users holding an active config; users who
  have invited someone), and the count the composer displays comes from the SAME query the worker
  walks, so the pre-flight number cannot disagree with the send;
- up to three inline buttons, each with an ``https://`` URL — validated on the way in, because
  Telegram rejects the whole message otherwise and the operator would learn that only from a silent
  failure in a worker log;
- an optional send time, deferred by arq rather than slept through in a request;
- every send is recorded in ``broadcast_logs`` at enqueue time, so a job that never ran shows in the
  history instead of vanishing;
- and an unsent message can be kept as a DRAFT, in the database rather than the browser, because
  the console is shared: one person drafts an announcement and another sends it.
"""

from __future__ import annotations

from datetime import UTC, datetime

from fastapi import APIRouter, HTTPException, Query, Request
from pydantic import BaseModel, Field, field_validator

from gozar.config.settings import get_settings
from gozar.db.models.enums import Language
from gozar.db.repositories.broadcast_draft import BroadcastDraftRepository
from gozar.db.repositories.broadcast_log import BroadcastLogRepository
from gozar.db.repositories.user import UserRepository
from gozar.web.dependencies import AdminUser, DbSession

router = APIRouter(prefix="/broadcast", tags=["broadcast"])

_LANG_CODES = {lang.value for lang in Language}
#: Telegram renders only a handful of inline buttons legibly under a broadcast; three is the
#: composer's own limit, and the server holds to it rather than trusting the client.
_MAX_BUTTONS = 3


def _parse_langs(codes: list[str]) -> list[Language]:
    """Validate language codes ⊆ {fa,en,ru}; ``[]`` ⇒ everyone. 422 on an unknown code."""
    bad = [c for c in codes if c not in _LANG_CODES]
    if bad:
        raise HTTPException(422, f"unknown language(s): {bad}")
    return [Language(c) for c in codes]


class AudienceOut(BaseModel):
    recipients: int


class BroadcastButton(BaseModel):
    text: str = Field(min_length=1, max_length=64)
    url: str = Field(min_length=1, max_length=512)

    @field_validator("url")
    @classmethod
    def _https(cls, value: str) -> str:
        """Telegram rejects a non-``https://`` inline URL and fails the WHOLE message, so a typo
        here would look like "the broadcast silently did nothing"."""
        if not value.startswith("https://"):
            raise ValueError("button URL must start with https://")
        return value


class BroadcastIn(BaseModel):
    text: str = Field(min_length=1, max_length=4096)  # Telegram's single-message text ceiling
    languages: list[str] = Field(default_factory=list)  # empty ⇒ everyone
    only_active: bool = False
    only_referrers: bool = False
    buttons: list[BroadcastButton] = Field(default_factory=list, max_length=_MAX_BUTTONS)
    #: When to start. Absent ⇒ now. A past instant is treated as now rather than rejected: the
    #: operator's clock and the server's need not agree to the second.
    scheduled_for: datetime | None = None


class BroadcastOut(BaseModel):
    queued: bool
    recipients: int
    log_id: int


class BroadcastLogOut(BaseModel):
    id: int
    body: str
    languages: str
    only_active: bool
    only_referrers: bool
    buttons: list[BroadcastButton] = Field(default_factory=list)
    status: str
    recipients: int
    sent: int
    failed: int
    removed: int
    scheduled_for: datetime | None
    created_at: datetime
    finished_at: datetime | None


@router.get("/", response_model=AudienceOut)
async def audience(
    request: Request,
    session: DbSession,
    admin: AdminUser,
    languages: str = Query(""),
    only_active: bool = Query(False),
    only_referrers: bool = Query(False),
) -> AudienceOut:
    """Recipient count for the chosen audience. ``languages`` is a comma-separated subset of
    {fa,en,ru} (empty ⇒ everyone), e.g. ``?languages=fa,en&only_active=true``."""
    langs = _parse_langs([c for c in languages.split(",") if c])
    return AudienceOut(
        recipients=await UserRepository(session).count_audience(
            langs, only_active=only_active, only_referrers=only_referrers
        )
    )


@router.get("/history", response_model=list[BroadcastLogOut])
async def history(session: DbSession, admin: AdminUser) -> list[BroadcastLogOut]:
    """Recent broadcasts and how each one went."""
    rows = await BroadcastLogRepository(session).list_recent()
    return [
        BroadcastLogOut(
            id=r.id,
            body=r.body,
            languages=r.languages,
            only_active=r.only_active,
            only_referrers=r.only_referrers,
            buttons=[BroadcastButton(**b) for b in (r.buttons or [])],
            status=r.status,
            recipients=r.recipients,
            sent=r.sent,
            failed=r.failed,
            removed=r.removed,
            scheduled_for=r.scheduled_for,
            created_at=r.created_at,
            finished_at=r.finished_at,
        )
        for r in rows
    ]


class DraftIn(BaseModel):
    """A broadcast in progress. Everything is optional except the body — a draft is by definition
    incomplete, so the send route's validation would be the wrong gate here."""

    id: int | None = None  # present ⇒ overwrite that draft rather than mint a second copy
    text: str = Field(min_length=1, max_length=4096)
    languages: list[str] = Field(default_factory=list)
    only_active: bool = False
    only_referrers: bool = False
    buttons: list[BroadcastButton] = Field(default_factory=list, max_length=_MAX_BUTTONS)
    #: The hour of day that was chosen, not an instant: an absolute time saved on Monday is in the
    #: past by Tuesday, and "21:00" is what the operator actually picked.
    send_hour: int | None = Field(default=None, ge=0, le=23)


class DraftOut(BaseModel):
    id: int
    title: str
    body: str
    languages: str
    only_active: bool
    only_referrers: bool
    buttons: list[BroadcastButton] = Field(default_factory=list)
    send_hour: int | None
    updated_at: datetime


def _draft_out(row: object) -> DraftOut:
    return DraftOut(
        id=row.id,  # type: ignore[attr-defined]
        title=row.title,  # type: ignore[attr-defined]
        body=row.body,  # type: ignore[attr-defined]
        languages=row.languages,  # type: ignore[attr-defined]
        only_active=row.only_active,  # type: ignore[attr-defined]
        only_referrers=row.only_referrers,  # type: ignore[attr-defined]
        buttons=[BroadcastButton(**b) for b in (row.buttons or [])],  # type: ignore[attr-defined]
        send_hour=row.send_hour,  # type: ignore[attr-defined]
        updated_at=row.updated_at,  # type: ignore[attr-defined]
    )


@router.get("/drafts", response_model=list[DraftOut])
async def list_drafts(session: DbSession, admin: AdminUser) -> list[DraftOut]:
    """Saved-but-unsent broadcasts, newest first."""
    rows = await BroadcastDraftRepository(session).list()
    return [_draft_out(r) for r in rows]


@router.post("/drafts", response_model=DraftOut)
async def save_draft(body: DraftIn, session: DbSession, admin: AdminUser) -> DraftOut:
    """Create a draft, or overwrite the one named by ``id``.

    Language codes are validated even here: a draft restored months later should not be the first
    time anyone finds out its audience was nonsense.
    """
    _parse_langs(body.languages)
    row = await BroadcastDraftRepository(session).save(
        id_=body.id,
        body=body.text,
        languages=",".join(body.languages),
        only_active=body.only_active,
        only_referrers=body.only_referrers,
        buttons=[b.model_dump() for b in body.buttons] or None,
        send_hour=body.send_hour,
    )
    await session.commit()
    # A commit expires the instance, and `updated_at` is a server default — reading it to build the
    # response would then be a lazy load from a sync attribute access, which under asyncio raises
    # MissingGreenlet rather than quietly issuing a query.
    await session.refresh(row)
    return _draft_out(row)


@router.delete("/drafts/{draft_id}", status_code=204)
async def delete_draft(draft_id: int, session: DbSession, admin: AdminUser) -> None:
    if not await BroadcastDraftRepository(session).delete(draft_id):
        raise HTTPException(404, "draft not found")
    await session.commit()


@router.post("/", response_model=BroadcastOut)
async def send_broadcast(
    body: BroadcastIn, request: Request, session: DbSession, admin: AdminUser
) -> BroadcastOut:
    arq = request.app.state.arq
    if arq is None:
        raise HTTPException(503, "broadcast worker is not configured")
    langs = _parse_langs(body.languages)
    recipients = await UserRepository(session).count_audience(
        langs, only_active=body.only_active, only_referrers=body.only_referrers
    )
    if recipients == 0:
        # A send to nobody is a mistake in the filters, not a job worth queueing — and it would
        # otherwise land in the history as a "successful" broadcast that reached zero people.
        raise HTTPException(422, "the chosen audience is empty")

    when = body.scheduled_for
    if when is not None and when.tzinfo is None:
        when = when.replace(tzinfo=UTC)
    if when is not None and when <= datetime.now(UTC):
        when = None  # already due — treat as "now" rather than deferring into the past

    buttons = [b.model_dump() for b in body.buttons]
    log = await BroadcastLogRepository(session).create(
        body=body.text,
        languages=",".join(body.languages),
        only_active=body.only_active,
        only_referrers=body.only_referrers,
        buttons=buttons or None,
        recipients=recipients,
        scheduled_for=when,
    )
    # Committed BEFORE the enqueue: the worker looks the row up by id, and a job that starts before
    # its own row is visible would find nothing to write its outcome into.
    await session.commit()

    owners = get_settings().owners
    progress_chat = owners[0] if owners else 0  # the worker pings this Telegram chat with progress
    await arq.enqueue_job(
        "broadcast_text",
        body.text,
        progress_chat,
        body.languages,
        body.only_active,
        body.only_referrers,
        buttons,
        log.id,
        _defer_until=when,
    )
    return BroadcastOut(queued=True, recipients=recipients, log_id=log.id)
