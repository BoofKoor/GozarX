"""Site-device repository — the only path to the ``site_devices`` table.

The site analogue of ``UserRepository``, keyed by the opaque device ``uuid`` (never a telegram id).
"""

from __future__ import annotations

from sqlalchemy import func, select

from gozar.db.handles import new_handle, normalize_handle
from gozar.db.models.site_device import SiteDevice, SiteDeviceStatus
from gozar.db.repositories.base import BaseRepository


class SiteDeviceRepository(BaseRepository):
    async def get(self, uuid: str) -> SiteDevice | None:
        return await self.session.get(SiteDevice, uuid)

    async def get_by_handle(self, handle: str) -> SiteDevice | None:
        """Resolve a public handle (e.g. an incoming ``?ref=`` value) back to its device."""
        return await self.session.scalar(
            select(SiteDevice).where(SiteDevice.handle == normalize_handle(handle))
        )

    async def _unique_handle(self) -> str:
        """A fresh handle not already taken. The DB unique constraint is the real backstop; this
        just avoids the retry in the overwhelmingly common (collision-free) case."""
        for _ in range(8):
            candidate = new_handle()
            exists = await self.session.scalar(
                select(SiteDevice.uuid).where(SiteDevice.handle == candidate)
            )
            if exists is None:
                return candidate
        return new_handle()

    async def create(
        self,
        uuid: str,
        *,
        fingerprint_hash: str | None = None,
        ip_bucket: str | None = None,
        referred_by: str | None = None,
    ) -> SiteDevice:
        device = SiteDevice(
            uuid=uuid,
            handle=await self._unique_handle(),
            fingerprint_hash=fingerprint_hash,
            ip_bucket=ip_bucket,
            referred_by=referred_by,
        )
        self.session.add(device)
        await self.session.flush()
        return device

    async def get_or_create(
        self,
        uuid: str,
        *,
        fingerprint_hash: str | None = None,
        ip_bucket: str | None = None,
        referred_by: str | None = None,
    ) -> tuple[SiteDevice, bool]:
        """Return (device, created). ``created`` is True only when a new row was inserted."""
        device = await self.get(uuid)
        if device is not None:
            return device, False
        created = await self.create(
            uuid,
            fingerprint_hash=fingerprint_hash,
            ip_bucket=ip_bucket,
            referred_by=referred_by,
        )
        return created, True

    async def delete(self, device: SiteDevice) -> None:
        """Hard-delete a device row (the P6 reset). ``site_claims`` + ``site_rewards`` follow via
        their ``ON DELETE CASCADE`` foreign keys."""
        await self.session.delete(device)
        await self.session.flush()

    async def get_by_site_panel_username(self, username: str) -> SiteDevice | None:
        """Reverse lookup for the panel webhook: map a site panel username back to its device."""
        return await self.session.scalar(
            select(SiteDevice).where(SiteDevice.site_panel_username == username)
        )

    async def list_active_with_panel(self) -> list[tuple[str, str]]:
        """``(uuid, site_panel_username)`` for every ``active_config`` device with a live panel
        account — the audience the site reconcile sweep (P7) probes for ended/limited trials."""
        rows = await self.session.execute(
            select(SiteDevice.uuid, SiteDevice.site_panel_username).where(
                SiteDevice.status == SiteDeviceStatus.active_config,
                SiteDevice.site_panel_username.is_not(None),
            )
        )
        return [(uuid, name) for uuid, name in rows.all() if name]

    async def count(self) -> int:
        """Total device identities ever minted — the site funnel's top ('visits')."""
        return int(await self.session.scalar(select(func.count()).select_from(SiteDevice)) or 0)

    async def count_by_status(self) -> dict[str, int]:
        """``{status: count}`` over all devices (available / active_config / blocked)."""
        rows = await self.session.execute(
            select(SiteDevice.status, func.count()).group_by(SiteDevice.status)
        )
        return {str(status): int(n) for status, n in rows.all()}
