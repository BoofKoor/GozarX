"""Config-log repository."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import func, select

from gozar.db.models.config_log import ConfigLog
from gozar.db.repositories.base import BaseRepository


class ConfigLogRepository(BaseRepository):
    async def add(self, user_id: int, location: str) -> ConfigLog:
        log = ConfigLog(user_id=user_id, location=location)
        self.session.add(log)
        await self.session.flush()
        return log

    async def count_for_user(self, user_id: int) -> int:
        return int(
            await self.session.scalar(
                select(func.count()).select_from(ConfigLog).where(ConfigLog.user_id == user_id)
            )
            or 0
        )

    async def count_for_user_since(self, user_id: int, since: datetime) -> int:
        """Count a user's claims at or after ``since`` (backs the daily-trial guard)."""
        return int(
            await self.session.scalar(
                select(func.count())
                .select_from(ConfigLog)
                .where(ConfigLog.user_id == user_id, ConfigLog.created_at >= since)
            )
            or 0
        )
