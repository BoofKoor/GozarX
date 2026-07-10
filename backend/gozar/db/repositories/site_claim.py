"""Site-claim repository — the site's ``config_logs`` (one row per delivered site config)."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import func, select

from gozar.db.models.site_claim import SiteClaim
from gozar.db.repositories.base import BaseRepository


class SiteClaimRepository(BaseRepository):
    async def add(self, device_uuid: str, location: str) -> SiteClaim:
        claim = SiteClaim(device_uuid=device_uuid, location=location)
        self.session.add(claim)
        await self.session.flush()
        return claim

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
            .order_by(SiteClaim.created_at.desc())
            .limit(1)
        )
