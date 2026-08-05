"""Broadcast-log repository — the only path to ``broadcast_logs``."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import UTC, datetime

from sqlalchemy import select

from gozar.db.models.broadcast_log import BroadcastLog, BroadcastStatus
from gozar.db.repositories.base import BaseRepository


class BroadcastLogRepository(BaseRepository):
    async def create(
        self,
        *,
        body: str,
        languages: str,
        only_active: bool,
        only_referrers: bool,
        buttons: list | None,
        recipients: int,
        scheduled_for: datetime | None = None,
    ) -> BroadcastLog:
        """Record a broadcast at ENQUEUE time, before the worker touches it.

        Written here rather than when the fan-out finishes: a broadcast that never runs — worker
        down, job lost — still shows in the history as stuck on ``queued`` instead of vanishing.
        """
        row = BroadcastLog(
            body=body,
            languages=languages,
            only_active=only_active,
            only_referrers=only_referrers,
            buttons=buttons,
            recipients=recipients,
            scheduled_for=scheduled_for,
            status=BroadcastStatus.scheduled if scheduled_for else BroadcastStatus.queued,
        )
        self.session.add(row)
        await self.session.flush()
        return row

    async def get(self, id_: int) -> BroadcastLog | None:
        return await self.session.get(BroadcastLog, id_)

    async def mark_sending(self, id_: int) -> None:
        row = await self.get(id_)
        if row is not None:
            row.status = BroadcastStatus.sending
            await self.session.flush()

    async def complete(
        self, id_: int, *, sent: int, failed: int, removed: int, ok: bool = True
    ) -> None:
        """Fill in the outcome. A missing row is not an error — the broadcast still happened, and
        failing the worker over a bookkeeping row would be worse than losing the record."""
        row = await self.get(id_)
        if row is None:
            return
        row.sent = sent
        row.failed = failed
        row.removed = removed
        row.status = BroadcastStatus.done if ok else BroadcastStatus.failed
        row.finished_at = datetime.now(UTC)
        await self.session.flush()

    async def list_recent(self, limit: int = 20) -> Sequence[BroadcastLog]:
        """Newest first. ``id.desc()`` tiebreaks the server-default ``created_at`` so two sends in
        the same instant order stably."""
        result = await self.session.scalars(
            select(BroadcastLog)
            .order_by(BroadcastLog.created_at.desc(), BroadcastLog.id.desc())
            .limit(limit)
        )
        return list(result.all())
