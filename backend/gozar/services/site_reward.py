"""Site reward claiming — the one-time grants (PWA install, notifications).

Each successful reward recomputes the device's full allowance and, if it holds a live trial, raises
the panel limit (the shared ``bump_live_trial`` — also the LIMITED->ACTIVE revive). One-time rewards
are guarded by the ``unique(device, reward_type)`` constraint (a repeat is a clean no-op). The push
reward additionally requires a real, active push subscription so the bonus can't be farmed without
actually opting in. The daily-streak bonus is NOT claimed here — it advances automatically from
consecutive config claims (see ``SiteTrialService.claim`` / ``site_economy.next_streak_count``). All
amounts come from the ``site_*`` settings.
"""

from __future__ import annotations

from dataclasses import dataclass

from redis.asyncio import Redis

from gozar.db.models.site_device import SiteDevice
from gozar.db.models.site_reward import SiteRewardType
from gozar.db.repositories.push_subscription import PushSubscriptionRepository
from gozar.db.repositories.site_reward import SiteRewardRepository
from gozar.remnawave import RemnawaveClient
from gozar.services.settings_service import SettingsService, SiteSettingKey
from gozar.services.site_economy import site_device_allowance_bytes
from gozar.services.site_trial import bump_live_trial
from gozar.services.trial import human_bytes

# One-time reward types -> the setting that holds their MB value.
_ONE_TIME = {
    SiteRewardType.pwa: SiteSettingKey.SITE_REWARD_PWA_MB,
    SiteRewardType.push: SiteSettingKey.SITE_REWARD_PUSH_MB,
}


@dataclass(frozen=True)
class RewardResult:
    ok: bool
    reason: str | None = None
    reward_type: str | None = None
    amount_mb: int | None = None
    streak_count: int | None = None
    streak_active: bool = False
    new_daily: str | None = None


class SiteRewardService:
    def __init__(
        self,
        reward_repo: SiteRewardRepository,
        settings: SettingsService,
        panel: RemnawaveClient,
        redis: Redis,
        push_repo: PushSubscriptionRepository,
    ) -> None:
        self._rewards = reward_repo
        self._settings = settings
        self._panel = panel
        self._redis = redis
        self._push = push_repo

    async def claim(self, device: SiteDevice, reward_type: str) -> RewardResult:
        if reward_type in _ONE_TIME:
            return await self._one_time(device, reward_type)
        return RewardResult(ok=False, reason="unknown_reward")

    async def _one_time(self, device: SiteDevice, reward_type: str) -> RewardResult:
        # The push reward is earned by ACTUALLY enabling notifications: refuse it unless a real
        # active subscription exists for this device (the SPA subscribes before claiming). This
        # closes the "grant on the client's word" gap — you can't farm the bonus without opting in.
        if reward_type == SiteRewardType.push and not await self._push.list_for_device(device.uuid):
            return RewardResult(ok=False, reason="not_subscribed", reward_type=reward_type)

        amount = await self._settings.get_int(_ONE_TIME[reward_type], 0)
        granted = await self._rewards.add(device.uuid, reward_type, amount)
        if not granted:
            return RewardResult(ok=False, reason="already_claimed", reward_type=reward_type)
        new_daily = await site_device_allowance_bytes(self._settings, device, self._rewards)
        await bump_live_trial(self._panel, self._redis, device, new_daily)
        return RewardResult(
            ok=True,
            reward_type=reward_type,
            amount_mb=amount,
            new_daily=human_bytes(new_daily),
        )
