"""Settings repository — raw string key→value; type coercion lives in the Phase 2 service."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert

from gozar.db.models.setting import Setting
from gozar.db.repositories.base import BaseRepository


class SettingsRepository(BaseRepository):
    async def get(self, key: str) -> str | None:
        setting = await self.session.get(Setting, key)
        return setting.value if setting is not None else None

    async def set(self, key: str, value: str) -> None:
        stmt = pg_insert(Setting).values(key=key, value=value)
        stmt = stmt.on_conflict_do_update(
            index_elements=[Setting.key],
            set_={"value": stmt.excluded.value},
        )
        await self.session.execute(stmt)

    async def all_as_dict(self) -> dict[str, str]:
        result = await self.session.scalars(select(Setting))
        return {s.key: s.value for s in result.all()}
