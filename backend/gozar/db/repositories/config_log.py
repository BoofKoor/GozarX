"""Config-log repository."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import case, delete, func, select

from gozar.db.models.config_log import ConfigLog
from gozar.db.models.user import User
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
        """Count a user's claims at or after ``since`` (backs the rolling-cooldown claim guard)."""
        return int(
            await self.session.scalar(
                select(func.count())
                .select_from(ConfigLog)
                .where(ConfigLog.user_id == user_id, ConfigLog.created_at >= since)
            )
            or 0
        )

    async def latest_created_at_for_user(self, user_id: int) -> datetime | None:
        """The user's most recent claim time — used to show the cooldown time-remaining."""
        return await self.session.scalar(
            select(func.max(ConfigLog.created_at)).where(ConfigLog.user_id == user_id)
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

    # --- analytics (Phase B) ---------------------------------------------------------------------
    async def active_user_count_since(self, since: datetime) -> int:
        """Distinct users who claimed at/after ``since`` — backs the DAU/WAU/MAU active-user tiles
        (a real activity signal, unlike a raw claim count)."""
        return int(
            await self.session.scalar(
                select(func.count(func.distinct(ConfigLog.user_id))).where(
                    ConfigLog.created_at >= since
                )
            )
            or 0
        )

    async def hourly_weekday_counts(
        self, since: datetime, tz: str = "Asia/Tehran"
    ) -> list[tuple[int, int, int]]:
        """Claims bucketed by (weekday, hour) in ``tz`` local time → ``[(dow, hour, count), …]``.
        Backs the activity heatmap. ``dow`` is Postgres' 0=Sunday..6=Saturday. Local time (not UTC)
        so 'when is the bot busy' matches the audience's clock."""
        local = func.timezone(tz, ConfigLog.created_at)
        dow = func.extract("dow", local).label("dow")
        hour = func.extract("hour", local).label("hour")
        rows = await self.session.execute(
            select(dow, hour, func.count())
            .where(ConfigLog.created_at >= since)
            .group_by(dow, hour)
        )
        return [(int(d), int(h), int(n)) for d, h, n in rows.all()]

    async def claims_per_user_buckets(self) -> dict[str, int]:
        """Histogram of lifetime claims per user → ``{"1": n, "2-3": n, "4-6": n, "7+": n}`` (only
        users who ever claimed). Separates one-timers from power users."""
        per_user = (
            select(func.count().label("c"))
            .select_from(ConfigLog)
            .group_by(ConfigLog.user_id)
            .subquery()
        )
        c = per_user.c.c
        bucket = case(
            (c == 1, "1"),
            (c <= 3, "2-3"),
            (c <= 6, "4-6"),
            else_="7+",
        ).label("bucket")
        rows = await self.session.execute(
            select(bucket, func.count()).select_from(per_user).group_by(bucket)
        )
        return {str(b): int(n) for b, n in rows.all()}

    async def first_claim_stats(self) -> tuple[float | None, int, int]:
        """``(median_hours, within_24h, total_claimers)`` for signup→first-claim. Median via
        ``percentile_cont``; the delta is already in hours so the 24h filter is a plain ``<= 24``.
        Backs the activation panel (how fast, and how many activate same-day)."""
        firsts = (
            select(
                ConfigLog.user_id.label("uid"),
                func.min(ConfigLog.created_at).label("fc"),
            )
            .group_by(ConfigLog.user_id)
            .subquery()
        )
        delta_h = (func.extract("epoch", firsts.c.fc - User.created_at) / 3600.0).label("dh")
        stmt = select(
            func.percentile_cont(0.5).within_group(delta_h.asc()),
            func.count().filter(delta_h <= 24),
            func.count(),
        ).select_from(firsts.join(User, User.telegram_id == firsts.c.uid))
        median, within, total = (await self.session.execute(stmt)).one()
        return (
            round(float(median), 1) if median is not None else None,
            int(within or 0),
            int(total or 0),
        )
