"""Content repository — raw rows only; rendering/caching lives in the Phase 2 service."""

from __future__ import annotations

from sqlalchemy import select
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

    async def upsert(self, key: str, language: Language, body: str) -> None:
        stmt = pg_insert(Content).values(key=key, language=language, body=body)
        stmt = stmt.on_conflict_do_update(
            index_elements=[Content.key, Content.language],
            set_={"body": stmt.excluded.body},
        )
        await self.session.execute(stmt)

    async def add_default(self, key: str, language: Language, body: str) -> None:
        """Insert a default only if (key, language) is absent — never clobbers admin edits."""
        stmt = pg_insert(Content).values(key=key, language=language, body=body)
        stmt = stmt.on_conflict_do_nothing(index_elements=[Content.key, Content.language])
        await self.session.execute(stmt)

    async def all(self) -> list[Content]:
        result = await self.session.scalars(select(Content))
        return list(result.all())
