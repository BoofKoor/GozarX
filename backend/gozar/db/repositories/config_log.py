"""Config-log repository."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from sqlalchemy import case, delete, func, select

from gozar.config.reporting import DISPLAY_TZ_NAME
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
        """Claims per LOCAL day at or after ``since`` → ``[(YYYY-MM-DD, count), …]`` ascending.
        Backs the dashboard activity chart (one grouped query)."""
        # Bucketed on the LOCAL calendar day (DISPLAY_TZ), not the UTC one: the operator reads
        # these on Iran time, so a UTC bucket split every one of their days 3.5 hours early.
        day = func.date(func.timezone(DISPLAY_TZ_NAME, ConfigLog.created_at)).label("day")
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

    async def distinct_locations(self, limit: int = 100) -> list[str]:
        """Every location a config has ever been claimed from, alphabetically.

        Drawn from `config_logs`, not from the configured location list: the filter must offer what
        the data actually contains, or picking a freshly-configured location returns an empty table
        and picking a retired one is impossible.
        """
        rows = await self.session.execute(
            select(ConfigLog.location).distinct().order_by(ConfigLog.location).limit(limit)
        )
        return [loc for (loc,) in rows.all() if loc]

    async def latest_locations(self, user_ids: list[int]) -> dict[int, str]:
        """The location of each listed user's most recent claim, in ONE query.

        The alternative — a query per row — is 25 round trips to paint one page of the users table.
        """
        if not user_ids:
            return {}
        latest = (
            select(
                ConfigLog.user_id.label("user_id"),
                ConfigLog.location.label("location"),
                func.row_number()
                .over(
                    partition_by=ConfigLog.user_id,
                    # id breaks the tie: two claims can share a timestamp to the microsecond after a
                    # reclaim, and an unstable pick would make the column flicker between reloads.
                    order_by=(ConfigLog.created_at.desc(), ConfigLog.id.desc()),
                )
                .label("rn"),
            )
            .where(ConfigLog.user_id.in_(user_ids))
            .subquery()
        )
        rows = await self.session.execute(
            select(latest.c.user_id, latest.c.location).where(latest.c.rn == 1)
        )
        return {int(uid): loc for uid, loc in rows.all()}

    async def recent_for_user(self, user_id: int, limit: int = 6) -> list[ConfigLog]:
        """A user's most recent claims, newest first — the record dialog's timeline."""
        rows = await self.session.scalars(
            select(ConfigLog)
            .where(ConfigLog.user_id == user_id)
            .order_by(ConfigLog.created_at.desc(), ConfigLog.id.desc())
            .limit(limit)
        )
        return list(rows.all())

    async def daily_counts_for_user(self, user_id: int, since: datetime) -> list[tuple[str, int]]:
        """One user's claims per LOCAL day — the record dialog's mini chart. Same day boundary as
        every other reported day, so the row and the dashboard cannot disagree about a date."""
        day = func.date(func.timezone(DISPLAY_TZ_NAME, ConfigLog.created_at)).label("day")
        rows = await self.session.execute(
            select(day, func.count())
            .where(ConfigLog.user_id == user_id, ConfigLog.created_at >= since)
            .group_by(day)
            .order_by(day)
        )
        return [(d.isoformat(), int(n)) for d, n in rows.all()]

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
        self, since: datetime, tz: str = DISPLAY_TZ_NAME
    ) -> list[tuple[int, int, int]]:
        """Claims bucketed by (weekday, hour) in ``tz`` local time → ``[(dow, hour, count), …]``.
        Backs the activity heatmap. ``dow`` is Postgres' 0=Sunday..6=Saturday. Local time (not UTC)
        so 'when is the bot busy' matches the audience's clock."""
        local = func.timezone(tz, ConfigLog.created_at)
        dow = func.extract("dow", local).label("dow")
        hour = func.extract("hour", local).label("hour")
        rows = await self.session.execute(
            select(dow, hour, func.count()).where(ConfigLog.created_at >= since).group_by(dow, hour)
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

    # --- period comparison + retention ------------------------------------------------------------
    async def count_between(self, start: datetime, end: datetime) -> int:
        """Claims in the half-open window ``[start, end)`` — the previous-period comparison twin of
        ``count_since``."""
        return int(
            await self.session.scalar(
                select(func.count())
                .select_from(ConfigLog)
                .where(ConfigLog.created_at >= start, ConfigLog.created_at < end)
            )
            or 0
        )

    async def active_user_count_between(self, start: datetime, end: datetime) -> int:
        """Distinct claimers in ``[start, end)`` — previous-period twin of
        ``active_user_count_since``."""
        return int(
            await self.session.scalar(
                select(func.count(func.distinct(ConfigLog.user_id))).where(
                    ConfigLog.created_at >= start, ConfigLog.created_at < end
                )
            )
            or 0
        )

    async def new_vs_returning_daily(self, since: datetime) -> list[tuple[str, int, int]]:
        """Per UTC day at/after ``since`` → ``[(day, first_time_claimers, returning_claimers), …]``.

        A day's claimer is "new" when that day is their FIRST-EVER claim day (computed over all
        history, not just the window — otherwise everyone looks new on the first day of the range).
        The daily claim count alone can't tell growth from repeat usage; this splits them.
        """
        firsts = (
            select(
                ConfigLog.user_id.label("uid"),
                func.date(func.timezone(DISPLAY_TZ_NAME, func.min(ConfigLog.created_at))).label(
                    "first_day"
                ),
            )
            .group_by(ConfigLog.user_id)
            .subquery()
        )
        day = func.date(func.timezone(DISPLAY_TZ_NAME, ConfigLog.created_at)).label("day")
        is_new = day == firsts.c.first_day
        rows = await self.session.execute(
            select(
                day,
                func.count(func.distinct(ConfigLog.user_id)).filter(is_new),
                func.count(func.distinct(ConfigLog.user_id)).filter(~is_new),
            )
            .select_from(ConfigLog)
            .join(firsts, firsts.c.uid == ConfigLog.user_id)
            .where(ConfigLog.created_at >= since)
            .group_by(day)
            .order_by(day)
        )
        return [(d.isoformat(), int(a), int(b)) for d, a, b in rows.all()]

    async def active_users_daily(self, since: datetime) -> list[tuple[str, int]]:
        """Distinct claimers per LOCAL day at/after ``since`` → ``[(day, users), …]``. DAU as a
        SERIES — the dashboard only ever had it as a single point-in-time number."""
        day = func.date(func.timezone(DISPLAY_TZ_NAME, ConfigLog.created_at)).label("day")
        rows = await self.session.execute(
            select(day, func.count(func.distinct(ConfigLog.user_id)))
            .where(ConfigLog.created_at >= since)
            .group_by(day)
            .order_by(day)
        )
        return [(d.isoformat(), int(n)) for d, n in rows.all()]

    async def weekly_retention_cohorts(
        self, weeks: int = 6
    ) -> list[tuple[str, int, dict[int, int]]]:
        """Weekly signup cohorts → ``[(week_iso, cohort_size, {week_offset: returners}), …]``.

        ``week_offset`` 0 is the signup week itself, 1 the following week, and so on. A user counts
        for an offset when they claimed at least once during that week. This is the one view that
        answers "do people come back?" — every existing panel measured a single moment instead.

        Only cohorts inside the last ``weeks`` weeks are returned, newest cohort last.
        """
        cohort_start = func.date_trunc("week", User.created_at)
        # The window boundary is computed in Python and bound as a normal parameter. Building it in
        # SQL needed an INTERVAL cast, which asyncpg rejects (it wants a timedelta, not a string).
        oldest = datetime.now(UTC) - timedelta(weeks=max(weeks, 1) - 1)
        window_start = func.date_trunc("week", oldest)

        sizes = await self.session.execute(
            select(cohort_start.label("cohort"), func.count())
            .where(cohort_start >= window_start)
            .group_by(cohort_start)
            .order_by(cohort_start)
        )
        cohort_sizes = [(c, int(n)) for c, n in sizes.all()]
        if not cohort_sizes:
            return []

        claim_week = func.date_trunc("week", ConfigLog.created_at)
        # Whole weeks between the cohort's week and the claim's week.
        offset = func.floor(
            func.extract("epoch", claim_week - cohort_start) / (7 * 24 * 3600)
        ).label("offset")
        rows = await self.session.execute(
            select(
                cohort_start.label("cohort"),
                offset,
                func.count(func.distinct(ConfigLog.user_id)),
            )
            .select_from(User)
            .join(ConfigLog, ConfigLog.user_id == User.telegram_id)
            .where(cohort_start >= window_start, claim_week >= cohort_start)
            .group_by(cohort_start, offset)
        )
        by_cohort: dict[object, dict[int, int]] = {}
        for cohort, off, n in rows.all():
            by_cohort.setdefault(cohort, {})[int(off)] = int(n)
        return [
            (cohort.date().isoformat(), size, by_cohort.get(cohort, {}))
            for cohort, size in cohort_sizes
        ]

    async def first_claim_stats(
        self,
        since: datetime | None = None,
        until: datetime | None = None,
    ) -> tuple[float | None, int, int]:
        """``(median_hours, within_24h, cohort_size)`` for signup→first-claim. Median via
        ``percentile_cont``; the delta is already in hours so the 24h filter is a plain ``<= 24``.

        The window bounds the user's FIRST CLAIM, not their signup — the cohort is "everyone who
        activated during this period", which is what makes the figure comparable to the same
        period before it. Called with no bounds it is the all-time figure.
        """
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
        if since is not None:
            stmt = stmt.where(firsts.c.fc >= since)
        if until is not None:
            stmt = stmt.where(firsts.c.fc < until)
        median, within, total = (await self.session.execute(stmt)).one()
        return (
            round(float(median), 1) if median is not None else None,
            int(within or 0),
            int(total or 0),
        )
