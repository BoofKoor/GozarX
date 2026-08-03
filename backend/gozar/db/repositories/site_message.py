"""Site contact-message repository — the only writer of the ``site_messages`` inbox.

P6 provides the write path (the public contact form → one row per submission); the admin
read / mark-read path lands with the 'website' admin section (P9).
"""

from __future__ import annotations

from sqlalchemy import func, or_, select, update
from sqlalchemy.sql import Select

from gozar.db.models.site_message import SiteMessage
from gozar.db.repositories.base import BaseRepository


def _message_filter(
    stmt: Select, unread_only: bool, search: str | None, locale: str | None
) -> Select:
    """Inbox filters: unread-only, a locale, and a substring search over subject / body / reply
    handle. Shared by the page and its count."""
    if unread_only:
        stmt = stmt.where(SiteMessage.read.is_(False))
    if locale:
        stmt = stmt.where(SiteMessage.locale == locale)
    if search and search.strip():
        like = f"%{search.strip()}%"
        stmt = stmt.where(
            or_(
                SiteMessage.subject.ilike(like),
                SiteMessage.body.ilike(like),
                SiteMessage.reply_handle.ilike(like),
            )
        )
    return stmt


class SiteMessageRepository(BaseRepository):
    async def add(
        self,
        *,
        subject: str,
        body: str,
        reply_handle: str | None,
        locale: str,
        device_uuid: str | None,
    ) -> SiteMessage:
        message = SiteMessage(
            subject=subject,
            body=body,
            reply_handle=reply_handle,
            locale=locale,
            device_uuid=device_uuid,
        )
        self.session.add(message)
        await self.session.flush()
        return message

    async def list_page(
        self,
        *,
        limit: int,
        offset: int,
        unread_only: bool = False,
        search: str | None = None,
        locale: str | None = None,
    ) -> list[SiteMessage]:
        """One inbox page, newest first (admin read path)."""
        stmt = _message_filter(select(SiteMessage), unread_only, search, locale)
        # id.desc() is the tiebreak: created_at is server_default now(), IDENTICAL for rows inserted
        # in one transaction, so ordering by it alone makes LIMIT/OFFSET paging drop/dup rows.
        stmt = stmt.order_by(SiteMessage.created_at.desc(), SiteMessage.id.desc())
        stmt = stmt.limit(limit).offset(offset)
        rows = await self.session.scalars(stmt)
        return list(rows.all())

    async def count(
        self,
        *,
        unread_only: bool = False,
        search: str | None = None,
        locale: str | None = None,
    ) -> int:
        """Rows matching the same filter the page uses, so the two can never disagree."""
        stmt = _message_filter(
            select(func.count()).select_from(SiteMessage), unread_only, search, locale
        )
        return int(await self.session.scalar(stmt) or 0)

    async def get(self, id_: int) -> SiteMessage | None:
        return await self.session.get(SiteMessage, id_)

    async def mark_read(self, id_: int) -> bool:
        """Flip one message to read. Returns True iff it existed and was unread (idempotent)."""
        result = await self.session.execute(
            update(SiteMessage)
            .where(SiteMessage.id == id_, SiteMessage.read.is_(False))
            .values(read=True)
        )
        return bool(result.rowcount)

    async def mark_unread(self, id_: int) -> bool:
        """Flip one message back to unread — "I'll deal with this later" needs to be expressible,
        and opening a message marks it read automatically."""
        result = await self.session.execute(
            update(SiteMessage)
            .where(SiteMessage.id == id_, SiteMessage.read.is_(True))
            .values(read=False)
        )
        return bool(result.rowcount)

    async def delete(self, message: SiteMessage) -> None:
        await self.session.delete(message)
        await self.session.flush()
