"""Site reward claiming — one-time grants (PWA install, notifications) + the daily-streak check-in.

Each successful reward recomputes the device's full allowance and, if it holds a live trial, raises
the panel limit (the shared ``bump_live_trial`` — also the LIMITED->ACTIVE revive). One-time rewards
are guarded by the ``unique(device, reward_type)`` constraint (a repeat is a clean no-op). The
streak is a consecutive-UTC-day check-in on the device row; its bonus stands while the streak holds.
All amounts come from the ``site_*`` settings.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from redis.asyncio import Redis

from gozar.db.models.site_device import SiteDevice
from gozar.db.models.site_reward import SiteRewardType
from gozar.db.repositories.site_reward import SiteRewardRepository
from gozar.remnawave import RemnawaveClient
from gozar.services.settings_service import SettingsService, SiteSettingKey
from gozar.services.site_economy import site_device_allowance_bytes, streak_is_active
from gozar.services.site_trial import bump_live_trial
from gozar.services.trial import human_bytes, start_of_today_utc

# One-time reward types -> the setting that holds their MB value.
_ONE_TIME = {
    SiteRewardType.pwa: SiteSettingKey.SITE_REWARD_PWA_MB,
    SiteRewardType.push: SiteSettingKey.SITE_REWARD_PUSH_MB,
}
_STREAK = "streak"


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
    ) -> None:
        self._rewards = reward_repo
        self._settings = settings
        self._panel = panel
        self._redis = redis

    async def claim(self, device: SiteDevice, reward_type: str) -> RewardResult:
        if reward_type in _ONE_TIME:
            return await self._one_time(device, reward_type)
        if reward_type == _STREAK:
            return await self._streak(device)
        return RewardResult(ok=False, reason="unknown_reward")

    async def _one_time(self, device: SiteDevice, reward_type: str) -> RewardResult:
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

    async def _streak(self, device: SiteDevice) -> RewardResult:
        today = start_of_today_utc()
        last = device.last_streak_at
        if last is not None and last.tzinfo is None:
            last = last.replace(tzinfo=UTC)
        last_day = last.date() if last else None

        if last_day == today.date():
            pass  # already checked in today — idempotent
        elif last_day == (today - timedelta(days=1)).date():
            device.streak_count += 1  # consecutive day
        else:
            device.streak_count = 1  # first visit or a broken streak restarts at 1
        device.last_streak_at = datetime.now(UTC)

        streak_days = await self._settings.get_int(SiteSettingKey.SITE_STREAK_DAYS, 0)
        active = streak_is_active(device, streak_days)
        new_daily = await site_device_allowance_bytes(self._settings, device, self._rewards)
        if active:
            # only bump UP (a lost streak never lowers a live trial mid-flight).
            await bump_live_trial(self._panel, self._redis, device, new_daily)
        return RewardResult(
            ok=True,
            reward_type=_STREAK,
            streak_count=device.streak_count,
            streak_active=active,
            new_daily=human_bytes(new_daily),
        )
