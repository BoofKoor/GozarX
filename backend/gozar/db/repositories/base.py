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


#: The escape character `contains_pattern` uses — pass it as ``ilike(..., escape=LIKE_ESCAPE)``.
LIKE_ESCAPE = "\\"


def contains_pattern(term: str) -> str:
    """A ``LIKE`` pattern matching ``term`` anywhere, with its own ``%`` and ``_`` taken LITERALLY.

    Interpolated raw, a search box was a wildcard language: ``_`` matched any one character, so
    looking for the handle ``g_12`` also returned ``gx12``, and ``%`` matched everything. Use with
    ``escape=LIKE_ESCAPE``.
    """
    escaped = (
        term.replace(LIKE_ESCAPE, LIKE_ESCAPE * 2)
        .replace("%", LIKE_ESCAPE + "%")
        .replace("_", LIKE_ESCAPE + "_")
    )
    return f"%{escaped}%"
