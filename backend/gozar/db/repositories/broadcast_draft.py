"""Broadcast-draft repository — the only path to ``broadcast_drafts``."""

from __future__ import annotations

from collections.abc import Sequence

from sqlalchemy import delete, select

from gozar.db.models.broadcast_draft import BroadcastDraft
from gozar.db.repositories.base import BaseRepository

#: How many drafts the list returns. A drafts box is a shelf, not an archive — past a couple of
#: dozen the operator wants the newest few and a delete button, not a pager.
LIST_LIMIT = 25
#: Where the auto-title is cut. Long enough to tell two announcements apart in a list.
TITLE_CHARS = 80


def title_for(body: str) -> str:
    """First line of the body, trimmed — so a draft never has to be named to be saved."""
    first = body.strip().splitlines()[0].strip() if body.strip() else ""
    return first[:TITLE_CHARS]


class BroadcastDraftRepository(BaseRepository):
    async def save(
        self,
        *,
        id_: int | None,
        body: str,
        languages: str,
        only_active: bool,
        only_referrers: bool,
        buttons: list | None,
        send_hour: int | None,
    ) -> BroadcastDraft:
        """Create a draft, or update the one named by ``id_``.

        One method for both because the composer does not distinguish: pressing save on a draft it
        restored should overwrite it, not mint a second copy of the same announcement each time.
        An ``id_`` that no longer exists (someone else deleted it) creates a new row rather than
        failing — the operator's text matters more than the identifier it used to have.
        """
        row = await self.get(id_) if id_ is not None else None
        if row is None:
            row = BroadcastDraft()
            self.session.add(row)
        row.title = title_for(body)
        row.body = body
        row.languages = languages
        row.only_active = only_active
        row.only_referrers = only_referrers
        row.buttons = buttons
        row.send_hour = send_hour
        await self.session.flush()
        return row

    async def get(self, id_: int) -> BroadcastDraft | None:
        return await self.session.get(BroadcastDraft, id_)

    async def list(self, limit: int = LIST_LIMIT) -> Sequence[BroadcastDraft]:
        """Newest first — the draft you were just working on is the one you want back."""
        result = await self.session.execute(
            select(BroadcastDraft).order_by(BroadcastDraft.updated_at.desc()).limit(limit)
        )
        return result.scalars().all()

    async def delete(self, id_: int) -> bool:
        """``True`` when a row was actually removed, so the route can 404 rather than lie."""
        result = await self.session.execute(delete(BroadcastDraft).where(BroadcastDraft.id == id_))
        return bool(result.rowcount)
