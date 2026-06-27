"""Button-config repository — admin overrides for the in-code button catalogue (Phase 7c)."""

from __future__ import annotations

from sqlalchemy import delete, func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert

from gozar.db.models.button_config import ButtonConfig
from gozar.db.repositories.base import BaseRepository


class ButtonConfigRepository(BaseRepository):
    async def all(self) -> list[ButtonConfig]:
        result = await self.session.scalars(select(ButtonConfig))
        return list(result.all())

    async def get(self, key: str) -> ButtonConfig | None:
        return await self.session.get(ButtonConfig, key)

    async def upsert(
        self,
        key: str,
        *,
        labels: dict[str, str] | None,
        is_visible: bool,
        row_index: int | None,
        position: int | None,
    ) -> None:
        stmt = pg_insert(ButtonConfig).values(
            key=key,
            labels=labels,
            is_visible=is_visible,
            row_index=row_index,
            position=position,
        )
        stmt = stmt.on_conflict_do_update(
            index_elements=[ButtonConfig.key],
            set_={
                "labels": stmt.excluded.labels,
                "is_visible": stmt.excluded.is_visible,
                "row_index": stmt.excluded.row_index,
                "position": stmt.excluded.position,
                "updated_at": func.now(),
            },
        )
        await self.session.execute(stmt)

    async def delete(self, key: str) -> None:
        """Remove the override → the button reverts to its code/catalogue default."""
        await self.session.execute(delete(ButtonConfig).where(ButtonConfig.key == key))
