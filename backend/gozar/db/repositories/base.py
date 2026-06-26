"""Base repository.

Holds the per-request ``AsyncSession``. Repositories ``flush`` (to surface DB errors and assign
generated PKs) but **never** ``commit`` — the per-update middleware (Phase 3) owns the transaction
boundary, so one update == one session == one commit/rollback.
"""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession


class BaseRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
