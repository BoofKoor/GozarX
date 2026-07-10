"""Site referral awarding — credit the inviter on an invitee device's FIRST claim.

The parallel of ``ReferralService`` for site devices. Runs inside the invitee's request session (the
inviter is loaded via the same session), so the inviter's ``referral_count += 1`` and the invitee's
``site_claim`` insert commit together — the +1 can't be dropped and a failure rolls back both. If
the inviter holds a live trial we raise its panel limit immediately (the shared ``bump_live_trial``,
also the LIMITED->ACTIVE revive path); that bump is best-effort. Never touches the bot ``users``
table — the two referral economies are fully separate.
"""

from __future__ import annotations

from dataclasses import dataclass

from redis.asyncio import Redis

from gozar.db.models.site_device import SiteDevice, SiteDeviceStatus
from gozar.db.repositories.site_device import SiteDeviceRepository
from gozar.db.repositories.site_reward import SiteRewardRepository
from gozar.remnawave import RemnawaveClient
from gozar.services.settings_service import SettingsService
from gozar.services.site_economy import site_device_allowance_bytes
from gozar.services.site_trial import bump_live_trial


@dataclass(frozen=True)
class SiteAwardResult:
    """A credited site referral — carried back so the caller can push the inviter a notice later.

    ``new_daily_bytes`` is the inviter's recomputed FULL allowance (capped referral bonus + their
    claimed rewards + streak), so any notice quotes an always-accurate number.
    """

    inviter_uuid: str
    new_count: int
    new_daily_bytes: int


class SiteReferralService:
    def __init__(
        self,
        device_repo: SiteDeviceRepository,
        reward_repo: SiteRewardRepository,
        settings: SettingsService,
        panel: RemnawaveClient,
        redis: Redis,
    ) -> None:
        self._devices = device_repo
        self._rewards = reward_repo
        self._settings = settings
        self._panel = panel
        self._redis = redis

    async def award_first_claim(self, invitee: SiteDevice) -> SiteAwardResult | None:
        """Credit the invitee's referrer (caller guarantees this is the invitee's first claim)."""
        if not invitee.referred_by:
            return None
        inviter = await self._devices.get(invitee.referred_by)
        if (
            inviter is None
            or inviter.uuid == invitee.uuid
            or inviter.status == SiteDeviceStatus.blocked
        ):
            return None

        inviter.referral_count += 1  # managed entity — persists on the request commit
        new_daily = await site_device_allowance_bytes(self._settings, inviter, self._rewards)
        await bump_live_trial(self._panel, self._redis, inviter, new_daily)
        return SiteAwardResult(inviter.uuid, inviter.referral_count, new_daily)
