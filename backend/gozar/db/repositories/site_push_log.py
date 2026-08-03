"""Site push-log repository — the only path to ``site_push_logs``."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import UTC, datetime

from sqlalchemy import func, select

from gozar.db.models.site_push_log import SitePushLog, SitePushStatus
from gozar.db.repositories.base import BaseRepository


class SitePushLogRepository(BaseRepository):
    async def create(
        self, *, title: str, body: str, url: str, locale: str | None, recipients: int
    ) -> SitePushLog:
        """Record a broadcast at ENQUEUE time, before the worker touches it.

        Writing the row here (rather than when the fan-out finishes) means a broadcast that never
        runs — worker down, job lost — still shows in the history as stuck on ``queued`` instead of
        vanishing without a trace.
        """
        row = SitePushLog(title=title, body=body, url=url, locale=locale, recipients=recipients)
        self.session.add(row)
        await self.session.flush()
        return row

    async def get(self, id_: int) -> SitePushLog | None:
        return await self.session.get(SitePushLog, id_)

    async def mark_sending(self, id_: int) -> None:
        row = await self.get(id_)
        if row is not None:
            row.status = SitePushStatus.sending
            await self.session.flush()

    async def complete(
        self, id_: int, *, sent: int, failed: int, pruned: int, ok: bool = True
    ) -> None:
        """Fill in the outcome. A missing row is not an error — the broadcast still happened, and
        failing the worker over a bookkeeping row would be worse than losing the record."""
        row = await self.get(id_)
        if row is None:
            return
        row.sent = sent
        row.failed = failed
        row.pruned = pruned
        row.status = SitePushStatus.done if ok else SitePushStatus.failed
        row.finished_at = datetime.now(UTC)
        await self.session.flush()

    async def list_recent(self, limit: int = 20) -> Sequence[SitePushLog]:
        """Newest broadcasts first. ``id.desc()`` tiebreaks the server-default ``created_at`` so two
        sends in the same instant order stably."""
        result = await self.session.scalars(
            select(SitePushLog)
            .order_by(SitePushLog.created_at.desc(), SitePushLog.id.desc())
            .limit(limit)
        )
        return result.all()

    async def count(self) -> int:
        return int(await self.session.scalar(select(func.count()).select_from(SitePushLog)) or 0)
