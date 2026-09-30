"""Content repository — raw rows only; rendering/caching lives in the Phase 2 service."""

from __future__ import annotations

from sqlalchemy import func, select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert

from gozar.db.models.content import Content
from gozar.db.models.enums import Language
from gozar.db.repositories.base import BaseRepository


class ContentRepository(BaseRepository):
    async def get(self, key: str, language: Language) -> Content | None:
        result = await self.session.scalars(
            select(Content).where(Content.key == key, Content.language == language)
        )
        return result.first()

    async def get_body(self, key: str, language: Language) -> str | None:
        row = await self.get(key, language)
        return row.body if row is not None else None

    async def get_message(self, key: str, language: Language) -> tuple[str, bool] | None:
        """The body plus its link-preview flag (or None if the (key, language) row is absent)."""
        row = await self.get(key, language)
        return (row.body, row.link_preview) if row is not None else None

    async def upsert(
        self, key: str, language: Language, body: str, link_preview: bool = True
    ) -> None:
        stmt = pg_insert(Content).values(
            key=key, language=language, body=body, link_preview=link_preview
        )
        stmt = stmt.on_conflict_do_update(
            index_elements=[Content.key, Content.language],
            set_={"body": stmt.excluded.body, "link_preview": stmt.excluded.link_preview},
        )
        await self.session.execute(stmt)

    async def add_default(self, key: str, language: Language, body: str) -> None:
        """Insert a default only if (key, language) is absent — never clobbers admin edits."""
        stmt = pg_insert(Content).values(key=key, language=language, body=body)
        stmt = stmt.on_conflict_do_nothing(index_elements=[Content.key, Content.language])
        await self.session.execute(stmt)

    async def restore_blank(self, key: str, language: Language, body: str) -> bool:
        """Write ``body`` over a row that exists but is BLANK; True when one was restored.

        Only for keys where blank is never a valid state (the seeded site copy, whose push nudges
        have nothing to fall back to). A blank bot translation means "use Persian"; leave it be.
        """
        result = await self.session.execute(
            update(Content)
            .where(
                Content.key == key,
                Content.language == language,
                func.btrim(Content.body) == "",
            )
            .values(body=body)
        )
        return bool(result.rowcount)

    async def all(self) -> list[Content]:
        result = await self.session.scalars(select(Content))
        return list(result.all())
