"""Site-claim repository — the site's ``config_logs`` (one row per delivered site config)."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime

from sqlalchemy import func, select

from gozar.db.models.site_claim import SiteClaim
from gozar.db.repositories.base import BaseRepository


class SiteClaimRepository(BaseRepository):
    async def add(self, device_uuid: str, location: str, *, is_change: bool = False) -> SiteClaim:
        """Log one delivery. ``is_change`` marks a change-location re-pick (vs the opening
        provision) so the admin funnel stats can exclude it — see ``SiteClaim.is_change``."""
        claim = SiteClaim(device_uuid=device_uuid, location=location, is_change=is_change)
        self.session.add(claim)
        await self.session.flush()
        return claim

    async def recent_for_device(self, device_uuid: str, limit: int = 8) -> Sequence[SiteClaim]:
        """The device's most recent deliveries (newest first) — the account 'claim history' list.
        id.desc() tiebreaks the server-default ``created_at`` so same-instant rows order stably."""
        result = await self.session.scalars(
            select(SiteClaim)
            .where(SiteClaim.device_uuid == device_uuid)
            .order_by(SiteClaim.created_at.desc(), SiteClaim.id.desc())
            .limit(limit)
        )
        return result.all()

    async def claim_times_for_device(self, device_uuid: str) -> list[datetime]:
        """Every claim timestamp for the device — the raw input to the derived daily-claim streak
        (``streak_from_claim_times`` collapses same-window change-location rows into days)."""
        result = await self.session.scalars(
            select(SiteClaim.created_at).where(SiteClaim.device_uuid == device_uuid)
        )
        return list(result.all())

    async def count_for_device(self, device_uuid: str) -> int:
        return int(
            await self.session.scalar(
                select(func.count())
                .select_from(SiteClaim)
                .where(SiteClaim.device_uuid == device_uuid)
            )
            or 0
        )

    async def latest_created_at_for_device(self, device_uuid: str) -> datetime | None:
        return await self.session.scalar(
            select(func.max(SiteClaim.created_at)).where(SiteClaim.device_uuid == device_uuid)
        )

    async def latest_location_for_device(self, device_uuid: str) -> str | None:
        """The location NAME of the device's most recent delivery — the 'current config' the status
        screen shows (its link is looked up in the cached subscription map by this name)."""
        return await self.session.scalar(
            select(SiteClaim.location)
            .where(SiteClaim.device_uuid == device_uuid)
            # id.desc() tiebreak: two claims can share created_at (server_default now()); without it
            # LIMIT 1 could pick the wrong one as the "current config".
            .order_by(SiteClaim.created_at.desc(), SiteClaim.id.desc())
            .limit(1)
        )

    # --- admin site funnel stats (grouped aggregates; mirror ConfigLogRepository) ----------------
    async def count_all(self) -> int:
        """Total site claims ever delivered — the public 'configs delivered' figure."""
        return int(await self.session.scalar(select(func.count()).select_from(SiteClaim)) or 0)

    async def count_since(self, since: datetime) -> int:
        """Provisions at or after ``since`` (admin stats: 'configs today'). Change-location re-picks
        are excluded so the figure counts trials opened, matching the bot's config_logs."""
        return int(
            await self.session.scalar(
                select(func.count())
                .select_from(SiteClaim)
                .where(SiteClaim.created_at >= since, SiteClaim.is_change.is_(False))
            )
            or 0
        )

    async def distinct_device_count(self) -> int:
        """How many distinct devices ever claimed ≥1 config — the funnel conversion numerator.
        (Every claimer has an opening provision, so this is unaffected by change-location rows.)"""
        return int(
            await self.session.scalar(select(func.count(func.distinct(SiteClaim.device_uuid)))) or 0
        )

    async def daily_counts(self, since: datetime) -> list[tuple[str, int]]:
        """Provisions per UTC day at/after ``since`` → ``[(YYYY-MM-DD, count), …]`` ascending.
        Excludes change-location re-picks (funnel metric — trials opened per day)."""
        day = func.date(SiteClaim.created_at).label("day")
        rows = await self.session.execute(
            select(day, func.count())
            .where(SiteClaim.created_at >= since, SiteClaim.is_change.is_(False))
            .group_by(day)
            .order_by(day)
        )
        return [(d.isoformat(), int(n)) for d, n in rows.all()]

    async def location_counts(self, since: datetime, limit: int = 10) -> list[tuple[str, int]]:
        """Provisions grouped by location at/after ``since`` → ``[(location, count), …]`` busiest
        first (matched by remark NAME). Change-location re-picks are excluded, so this reflects the
        location each trial OPENED with (consistent with the bot's config_logs)."""
        count = func.count().label("n")
        rows = await self.session.execute(
            select(SiteClaim.location, count)
            .where(SiteClaim.created_at >= since, SiteClaim.is_change.is_(False))
            .group_by(SiteClaim.location)
            .order_by(count.desc())
            .limit(limit)
        )
        return [(loc, int(n)) for loc, n in rows.all()]
