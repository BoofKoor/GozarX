"""Site-reward repository — one-time reward grants (PWA install, notifications) per device.

The ``unique(device_uuid, reward_type)`` constraint makes a double-claim a no-op: ``add`` uses
ON CONFLICT DO NOTHING and reports whether a row was actually inserted. Repeatable bonuses (invites,
streak) are NOT rows here — they live on ``site_devices`` and are read straight off the device.
"""

from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert

from gozar.db.models.site_reward import SiteReward
from gozar.db.repositories.base import BaseRepository


class SiteRewardRepository(BaseRepository):
    async def add(self, device_uuid: str, reward_type: str, amount_mb: int) -> bool:
        """Grant a one-time reward. Returns True if newly granted, False if already claimed."""
        stmt = (
            pg_insert(SiteReward)
            .values(device_uuid=device_uuid, reward_type=reward_type, amount_mb=amount_mb)
            .on_conflict_do_nothing(index_elements=[SiteReward.device_uuid, SiteReward.reward_type])
        )
        result = await self.session.execute(stmt)
        return bool(result.rowcount)

    async def has(self, device_uuid: str, reward_type: str) -> bool:
        found = await self.session.scalar(
            select(SiteReward.id).where(
                SiteReward.device_uuid == device_uuid, SiteReward.reward_type == reward_type
            )
        )
        return found is not None

    async def types_for_device(self, device_uuid: str) -> set[str]:
        """The one-time reward types this device has claimed — feeds the quota math."""
        rows = await self.session.scalars(
            select(SiteReward.reward_type).where(SiteReward.device_uuid == device_uuid)
        )
        return set(rows.all())

    async def totals_by_type(self) -> list[tuple[str, int, int]]:
        """Per one-time reward type → ``[(type, grants, total_mb), …]`` — the recorded reward
        economy (PWA install / push opt-in). Repeatable invite & streak MB are modeled from the
        device counters, not stored here, so this is only the one-time grants."""
        rows = await self.session.execute(
            select(
                SiteReward.reward_type,
                func.count(),
                func.coalesce(func.sum(SiteReward.amount_mb), 0),
            ).group_by(SiteReward.reward_type)
        )
        return [(str(t), int(c), int(mb)) for t, c, mb in rows.all()]
