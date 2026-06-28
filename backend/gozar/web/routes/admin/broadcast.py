"""Admin broadcast (auth-gated) — compose a text message and send it to the chosen audience.

The bot's ``/admin`` copies/forwards a Telegram message; the web panel has no source message, so it
composes text and enqueues the ``broadcast_text`` worker job (same "never drop a user on a transient
error" allowlist as the bot fan-out). A ``languages`` filter (empty ⇒ everyone) targets specific
language groups, so a different message can be sent to each. Live progress is reported to the first
configured owner in Telegram; delivery happens in the worker, never in this request.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query, Request
from pydantic import BaseModel, Field

from gozar.config.settings import get_settings
from gozar.db.models.enums import Language
from gozar.db.repositories.user import UserRepository
from gozar.web.dependencies import AdminUser, DbSession

router = APIRouter(prefix="/broadcast", tags=["broadcast"])

_LANG_CODES = {lang.value for lang in Language}


def _parse_langs(codes: list[str]) -> list[Language]:
    """Validate language codes ⊆ {fa,en,ru}; ``[]`` ⇒ everyone. 422 on an unknown code."""
    bad = [c for c in codes if c not in _LANG_CODES]
    if bad:
        raise HTTPException(422, f"unknown language(s): {bad}")
    return [Language(c) for c in codes]


class AudienceOut(BaseModel):
    recipients: int


class BroadcastIn(BaseModel):
    text: str = Field(min_length=1, max_length=4096)  # Telegram's single-message text ceiling
    languages: list[str] = Field(default_factory=list)  # empty ⇒ everyone


class BroadcastOut(BaseModel):
    queued: bool
    recipients: int


@router.get("/", response_model=AudienceOut)
async def audience(
    request: Request,
    session: DbSession,
    admin: AdminUser,
    languages: str = Query(""),
) -> AudienceOut:
    """Recipient count for the chosen audience. ``languages`` is a comma-separated subset of
    {fa,en,ru} (empty ⇒ everyone), e.g. ``?languages=fa,en``."""
    codes = [c for c in languages.split(",") if c]
    langs = _parse_langs(codes)
    return AudienceOut(recipients=await UserRepository(session).count_by_languages(langs))


@router.post("/", response_model=BroadcastOut)
async def send_broadcast(
    body: BroadcastIn, request: Request, session: DbSession, admin: AdminUser
) -> BroadcastOut:
    arq = request.app.state.arq
    if arq is None:
        raise HTTPException(503, "broadcast worker is not configured")
    langs = _parse_langs(body.languages)
    owners = get_settings().owners
    progress_chat = owners[0] if owners else 0  # the worker pings this Telegram chat with progress
    await arq.enqueue_job("broadcast_text", body.text, progress_chat, body.languages)
    return BroadcastOut(
        queued=True, recipients=await UserRepository(session).count_by_languages(langs)
    )
