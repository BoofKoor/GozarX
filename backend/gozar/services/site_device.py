"""Site device-lifecycle service — the irreversible 'reset this device' wipe (P6).

Frees the device's live panel trial (best-effort, single bounded call), drops its cached sub and
nudge guard, then hard-deletes the ``site_devices`` row — ``site_claims`` + ``site_rewards``
cascade via their foreign keys. The route clears the (httpOnly) device cookie afterward so the
browser mints a fresh identity next load. Never touches the bot ``users`` table.
"""

from __future__ import annotations

import logging

from redis.asyncio import Redis

from gozar.cache.redis import site_limited_notified_key, site_sub_cache_key
from gozar.db.models.site_device import SiteDevice
from gozar.db.repositories.site_device import SiteDeviceRepository
from gozar.remnawave import RemnawaveClient, RemnawaveError

logger = logging.getLogger("gozar.web.public")


class SiteDeviceService:
    def __init__(
        self, device_repo: SiteDeviceRepository, panel: RemnawaveClient, redis: Redis
    ) -> None:
        self._devices = device_repo
        self._panel = panel
        self._redis = redis

    async def reset(self, device: SiteDevice) -> None:
        """Irreversibly wipe ``device``: free its panel trial (best-effort), clear its Redis state,
        then delete the row (claims + rewards cascade). Panel failure is logged and ignored — the
        local wipe still proceeds so a reset is never blocked by an unreachable panel."""
        if device.site_panel_username:
            try:
                await self._panel.delete_user_by_username(device.site_panel_username)
            except RemnawaveError:
                logger.warning("site reset: panel delete failed for device %s", device.uuid)
        await self._redis.delete(site_sub_cache_key(device.uuid))
        await self._redis.delete(site_limited_notified_key(device.uuid))
        await self._devices.delete(device)
