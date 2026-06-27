"""Admin broadcast (auth-gated) — compose a text message and send it to every user.

The bot's ``/admin`` copies/forwards a Telegram message; the web panel has no source message, so it
composes text and enqueues the ``broadcast_text`` worker job (same "never drop a user on a transient
error" allowlist as the bot fan-out). Live progress is reported to the first configured owner in
Telegram; delivery happens in the worker, never in this request.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from gozar.config.settings import get_settings
from gozar.db.repositories.user import UserRepository
from gozar.web.dependencies import AdminUser, DbSession

router = APIRouter(prefix="/broadcast", tags=["broadcast"])


class AudienceOut(BaseModel):
    recipients: int


class BroadcastIn(BaseModel):
    text: str = Field(min_length=1, max_length=4096)  # Telegram's single-message text ceiling


class BroadcastOut(BaseModel):
    queued: bool
    recipients: int


@router.get("/", response_model=AudienceOut)
async def audience(request: Request, session: DbSession, admin: AdminUser) -> AudienceOut:
    return AudienceOut(recipients=await UserRepository(session).count())


@router.post("/", response_model=BroadcastOut)
async def send_broadcast(
    body: BroadcastIn, request: Request, session: DbSession, admin: AdminUser
) -> BroadcastOut:
    arq = request.app.state.arq
    if arq is None:
        raise HTTPException(503, "broadcast worker is not configured")
    owners = get_settings().owners
    progress_chat = owners[0] if owners else 0  # the worker pings this Telegram chat with progress
    await arq.enqueue_job("broadcast_text", body.text, progress_chat)
    return BroadcastOut(queued=True, recipients=await UserRepository(session).count())
