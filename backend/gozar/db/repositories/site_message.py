"""Site contact-message repository — the only writer of the ``site_messages`` inbox.

P6 provides the write path (the public contact form → one row per submission); the admin
read / mark-read path lands with the 'website' admin section (P9).
"""

from __future__ import annotations

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
