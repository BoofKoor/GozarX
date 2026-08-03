"""Website contact inbox (auth-gated) — read the ``site_messages`` from the public contact form.

Read + mark-read only (the public form is the sole writer). Message fields are ATTACKER-supplied and
returned verbatim; the admin panel MUST render them as plain text (never as HTML / never
``dangerouslySetInnerHTML``).
"""

from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, HTTPException, Query, Request, status
from pydantic import BaseModel

from gozar.db.models.site_message import SiteMessage
from gozar.db.repositories.site_message import SiteMessageRepository
from gozar.web.dependencies import AdminUser, DbSession

router = APIRouter(prefix="/site/inbox", tags=["site-inbox"])


class MessageOut(BaseModel):
    id: int
    subject: str
    body: str
    reply_handle: str | None
    locale: str
    device_uuid: str | None
    read: bool
    created_at: datetime | None


class MessagePage(BaseModel):
    items: list[MessageOut]
    total: int  # every message, regardless of filter
    matching: int  # rows matching the ACTIVE filter — what the pager divides by
    unread: int
    page: int
    page_size: int


def _out(m: SiteMessage) -> MessageOut:
    return MessageOut(
        id=m.id,
        subject=m.subject,
        body=m.body,
        reply_handle=m.reply_handle,
        locale=m.locale,
        device_uuid=m.device_uuid,
        read=m.read,
        created_at=m.created_at,
    )


@router.get("/", response_model=MessagePage)
async def list_messages(
    request: Request,
    session: DbSession,
    admin: AdminUser,
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=100),
    unread: bool = Query(False),
    search: str | None = Query(None),
    locale: str | None = Query(None),
) -> MessagePage:
    repo = SiteMessageRepository(session)
    offset = (page - 1) * page_size
    items = await repo.list_page(
        limit=page_size, offset=offset, unread_only=unread, search=search, locale=locale
    )
    return MessagePage(
        items=[_out(m) for m in items],
        # `matching` is what the pager must divide by: `total` counts EVERY message, so with a
        # search or a locale filter active it would show phantom pages past the real end.
        total=await repo.count(),
        matching=await repo.count(unread_only=unread, search=search, locale=locale),
        unread=await repo.count(unread_only=True),
        page=page,
        page_size=page_size,
    )


@router.post("/{message_id}/read", response_model=MessageOut)
async def mark_message_read(
    message_id: int, request: Request, session: DbSession, admin: AdminUser
) -> MessageOut:
    repo = SiteMessageRepository(session)
    await repo.mark_read(message_id)  # idempotent; a missing id simply matches no row
    message = await repo.get(message_id)
    if message is None:
        raise HTTPException(404, "message not found")
    return _out(message)


@router.post("/{message_id}/unread", response_model=MessageOut)
async def mark_message_unread(
    message_id: int, request: Request, session: DbSession, admin: AdminUser
) -> MessageOut:
    """Flip a message back to unread. Opening one marks it read automatically, so without this
    "leave it for later" was impossible once you had glanced at it."""
    repo = SiteMessageRepository(session)
    await repo.mark_unread(message_id)
    message = await repo.get(message_id)
    if message is None:
        raise HTTPException(404, "message not found")
    return _out(message)


@router.delete("/{message_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_message(
    message_id: int, request: Request, session: DbSession, admin: AdminUser
) -> None:
    """Drop a message for good — the inbox is the public contact form's only sink, so it collects
    spam that nothing could previously remove."""
    repo = SiteMessageRepository(session)
    message = await repo.get(message_id)
    if message is None:
        raise HTTPException(404, "message not found")
    await repo.delete(message)
