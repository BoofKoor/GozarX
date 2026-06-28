"""Config-log repository."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import delete, func, select

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

    async def distinct_user_count(self) -> int:
        """How many distinct users have ever claimed ≥1 config — the conversion numerator."""
        return int(
            await self.session.scalar(select(func.count(func.distinct(ConfigLog.user_id)))) or 0
        )

    async def count_since(self, since: datetime) -> int:
        """Total claims across all users at or after ``since`` (admin stats: 'configs today')."""
        return int(
            await self.session.scalar(
                select(func.count()).select_from(ConfigLog).where(ConfigLog.created_at >= since)
            )
            or 0
        )

    async def daily_counts(self, since: datetime) -> list[tuple[str, int]]:
        """Claims per UTC day at or after ``since`` → ``[(YYYY-MM-DD, count), …]`` ascending.
        Backs the dashboard activity chart (one grouped query)."""
        day = func.date(ConfigLog.created_at).label("day")
        rows = await self.session.execute(
            select(day, func.count())
            .where(ConfigLog.created_at >= since)
            .group_by(day)
            .order_by(day)
        )
        return [(d.isoformat(), int(n)) for d, n in rows.all()]

    async def location_counts(self, since: datetime, limit: int = 10) -> list[tuple[str, int]]:
        """Claims grouped by location at/after ``since`` → ``[(location, count), …]`` busiest first.
        Backs the dashboard 'top locations' bar (one grouped query)."""
        count = func.count().label("n")
        rows = await self.session.execute(
            select(ConfigLog.location, count)
            .where(ConfigLog.created_at >= since)
            .group_by(ConfigLog.location)
            .order_by(count.desc())
            .limit(limit)
        )
        return [(loc, int(n)) for loc, n in rows.all()]

    async def delete_for_user_since(self, user_id: int, since: datetime) -> int:
        """Drop a user's claims at or after ``since`` — the admin 'reclaim' action clears today's
        guard so the user can claim again. Returns the number of rows removed."""
        result = await self.session.execute(
            delete(ConfigLog).where(ConfigLog.user_id == user_id, ConfigLog.created_at >= since)
        )
        return int(result.rowcount or 0)
