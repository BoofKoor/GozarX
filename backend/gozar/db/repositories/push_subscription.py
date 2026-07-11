"""Push-subscription repository — the site's Web Push endpoints (its non-Telegram delivery channel).

``upsert`` dedupes on the unique ``endpoint`` (a browser re-subscribing reuses the same endpoint):
it re-points the row to the current device, refreshes the keys + locale, and re-activates it. A
subscription is pruned ONLY when the push service reports it permanently gone (404/410) — never on a
transient error (the v1 mass-deletion lesson); the sender maps that to ``deactivate``.
"""

from __future__ import annotations

from sqlalchemy import func, select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert

from gozar.db.models.push_subscription import PushSubscription
from gozar.db.repositories.base import BaseRepository


class PushSubscriptionRepository(BaseRepository):
    async def upsert(
        self, *, device_uuid: str, endpoint: str, p256dh: str, auth: str, locale: str
    ) -> None:
        """Store (or refresh) a subscription, keyed by its unique endpoint. A re-subscribe re-points
        the row to the current device, updates the keys + locale, and re-activates it."""
        stmt = (
            pg_insert(PushSubscription)
            .values(
                device_uuid=device_uuid,
                endpoint=endpoint,
                p256dh=p256dh,
                auth=auth,
                locale=locale,
                active=True,
            )
            .on_conflict_do_update(
                index_elements=[PushSubscription.endpoint],
                set_={
                    "device_uuid": device_uuid,
                    "p256dh": p256dh,
                    "auth": auth,
                    "locale": locale,
                    "active": True,
                },
            )
        )
        await self.session.execute(stmt)

    async def deactivate(self, endpoint: str) -> None:
        """Mark a subscription inactive — the toggle-off path and the 404/410 prune. Kept (not
        deleted) so a later re-subscribe with the same endpoint cleanly reactivates the row."""
        await self.session.execute(
            update(PushSubscription)
            .where(PushSubscription.endpoint == endpoint)
            .values(active=False)
        )

    async def list_for_device(self, device_uuid: str) -> list[PushSubscription]:
        """A device's ACTIVE subscriptions — the audience for a targeted nudge (expiry / volume)."""
        rows = await self.session.scalars(
            select(PushSubscription).where(
                PushSubscription.device_uuid == device_uuid,
                PushSubscription.active.is_(True),
            )
        )
        return list(rows.all())

    async def list_active(self) -> list[PushSubscription]:
        """Every ACTIVE subscription — the audience for a site push broadcast (arq worker)."""
        rows = await self.session.scalars(
            select(PushSubscription).where(PushSubscription.active.is_(True))
        )
        return list(rows.all())

    async def count_active(self) -> int:
        """How many active subscriptions — the push-broadcast recipient echo (admin panel)."""
        return int(
            await self.session.scalar(
                select(func.count())
                .select_from(PushSubscription)
                .where(PushSubscription.active.is_(True))
            )
            or 0
        )
