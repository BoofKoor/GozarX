"""Site-admin service — the moderation actions behind the panel's website device browser.

The parallel of ``AdminService`` for site devices. The website had no admin surface at all: its
users (handle, streak, invites, panel account, IP bucket, fingerprint) were invisible, the
anti-abuse panel reported "N devices share a fingerprint" while naming none of them, and there was
no way to stop an abuser short of the public reset endpoint.

Logic lives here, not in the route, so the same actions can be reused (a future in-bot command, a
worker sweep) without importing FastAPI — the one-directional import rule in CLAUDE.md.

Deliberately NO hard delete: ``blocked`` is reversible and keeps the anti-abuse trail (fingerprint,
IP bucket, claim history) that made the device worth looking at. The public ``SiteDeviceService``
still owns the irreversible user-initiated wipe.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime

from redis.asyncio import Redis

from gozar.cache.redis import site_limited_notified_key, site_sub_cache_key
from gozar.db.models.site_claim import SiteClaim
from gozar.db.models.site_device import SiteDevice, SiteDeviceStatus
from gozar.db.repositories.site_claim import SiteClaimRepository
from gozar.db.repositories.site_device import SiteDeviceRepository
from gozar.db.repositories.site_reward import SiteRewardRepository
from gozar.remnawave import RemnawaveClient, RemnawaveError

logger = logging.getLogger("gozar.web.admin.site")


@dataclass(frozen=True)
class SiteDeviceCard:
    """One device plus everything the detail drawer shows, gathered in one place."""

    device: SiteDevice
    claims: int
    recent_claims: list[SiteClaim]
    rewards: list[str]
    invited: int
    fingerprint_peers: list[SiteDevice]
    last_claim_at: datetime | None


class SiteAdminService:
    def __init__(
        self,
        devices: SiteDeviceRepository,
        claims: SiteClaimRepository,
        rewards: SiteRewardRepository,
        panel: RemnawaveClient,
        redis: Redis,
    ) -> None:
        self._devices = devices
        self._claims = claims
        self._rewards = rewards
        self._panel = panel
        self._redis = redis

    async def card(self, uuid: str) -> SiteDeviceCard | None:
        device = await self._devices.get(uuid)
        if device is None:
            return None
        return SiteDeviceCard(
            device=device,
            claims=await self._claims.count_for_device(uuid),
            recent_claims=list(await self._claims.recent_for_device(uuid)),
            rewards=sorted(await self._rewards.types_for_device(uuid)),
            invited=await self._devices.count_referred_by(uuid),
            fingerprint_peers=await self._devices.list_fingerprint_peers(
                device.fingerprint_hash, uuid
            ),
            last_claim_at=await self._claims.latest_created_at_for_device(uuid),
        )

    async def block(self, uuid: str) -> SiteDevice | None:
        """Stop this device claiming, and revoke what it already holds.

        Mirrors the bot's ban: free the live panel account first (best-effort, one bounded call —
        never a retry loop), then flip the status. Panel failure is logged and ignored, or an
        unreachable panel would make an abuser unblockable.
        """
        device = await self._devices.get(uuid)
        if device is None:
            return None
        await self._revoke_panel(device)
        device.status = SiteDeviceStatus.blocked
        device.site_panel_username = None
        return device

    async def unblock(self, uuid: str) -> SiteDevice | None:
        device = await self._devices.get(uuid)
        if device is None:
            return None
        device.status = SiteDeviceStatus.available
        return device

    async def reset_trial(self, uuid: str) -> SiteDevice | None:
        """Forgiveness: free the current trial and clear the rolling cooldown so the device can
        claim again right away. The device row, its claim history and its rewards all stay — this
        is the "let them through" action, not a wipe."""
        device = await self._devices.get(uuid)
        if device is None:
            return None
        await self._revoke_panel(device)
        device.status = SiteDeviceStatus.available
        device.site_panel_username = None
        # last_claim_at is the cooldown anchor; clearing it is what actually lets them re-claim.
        device.last_claim_at = None
        return device

    async def _revoke_panel(self, device: SiteDevice) -> None:
        """Best-effort: delete the live panel account and drop the cached subscription."""
        if device.site_panel_username:
            try:
                await self._panel.delete_user_by_username(device.site_panel_username)
            except RemnawaveError:
                logger.warning("site admin: panel delete failed for device %s", device.uuid)
        await self._redis.delete(site_sub_cache_key(device.uuid))
        await self._redis.delete(site_limited_notified_key(device.uuid))
