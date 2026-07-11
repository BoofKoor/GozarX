"""Site contact-message repository — the only writer of the ``site_messages`` inbox.

P6 provides the write path (the public contact form → one row per submission); the admin
read / mark-read path lands with the 'website' admin section (P9).
"""

from __future__ import annotations

from sqlalchemy import func, select, update

from gozar.db.models.site_message import SiteMessage
from gozar.db.repositories.base import BaseRepository


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
        self, *, limit: int, offset: int, unread_only: bool = False
    ) -> list[SiteMessage]:
        """One inbox page, newest first (admin read path)."""
        stmt = select(SiteMessage)
        if unread_only:
            stmt = stmt.where(SiteMessage.read.is_(False))
        stmt = stmt.order_by(SiteMessage.created_at.desc()).limit(limit).offset(offset)
        rows = await self.session.scalars(stmt)
        return list(rows.all())

    async def count(self, *, unread_only: bool = False) -> int:
        stmt = select(func.count()).select_from(SiteMessage)
        if unread_only:
            stmt = stmt.where(SiteMessage.read.is_(False))
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
