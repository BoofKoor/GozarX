"""Website trial economics — the site's quota math, driven entirely by the ``site_*`` settings.

The site analogue of ``trial.compute_traffic_bytes``: it reads the ``site_*`` keys (NOT the bot's),
so the two economies are fully independent. This is the single source of the site quota — reused by
site claim flow (P3), the referral live-bump (P5), and the status "next allowance" quote (P4). Never
hardcodes a reward/cap; every number comes from settings.
"""

from __future__ import annotations

from collections.abc import Collection
from datetime import UTC, datetime, timedelta

from gozar.db.models.site_device import SiteDevice
from gozar.db.models.site_reward import SiteRewardType
from gozar.db.repositories.site_reward import SiteRewardRepository
from gozar.services.settings_service import SettingsService, SiteSettingKey

# Fallbacks used ONLY if the (seeded) setting is missing — not a place to encode economics.
_DEFAULT_SITE_DAILY_MB = 1024
_MB = 1024 * 1024


async def site_compute_traffic_bytes(
    settings: SettingsService,
    referral_count: int,
    *,
    rewards: Collection[str] = (),
    streak_active: bool = False,
) -> int:
    """Site daily allowance in bytes: base + capped referral bonus + claimed one-time rewards
    (PWA / notifications) + the standing daily-streak bonus.

    ``rewards`` is the set of one-time reward types the device has already claimed
    (``SiteRewardType.pwa`` / ``.push``); ``streak_active`` adds the streak bonus while the device
    is on a qualifying streak. All amounts come from the ``site_*`` settings.
    """
    daily_mb = await settings.get_int(SiteSettingKey.SITE_DAILY_LIMIT_MB, _DEFAULT_SITE_DAILY_MB)
    reward_mb = await settings.get_int(SiteSettingKey.SITE_REFERRAL_REWARD_MB, 0)
    cap = await settings.get_int(SiteSettingKey.SITE_REFERRAL_REWARD_LIMIT, 0)
    rewarded = min(max(referral_count, 0), max(cap, 0))
    total_mb = daily_mb + rewarded * reward_mb

    if SiteRewardType.pwa in rewards:
        total_mb += await settings.get_int(SiteSettingKey.SITE_REWARD_PWA_MB, 0)
    if SiteRewardType.push in rewards:
        total_mb += await settings.get_int(SiteSettingKey.SITE_REWARD_PUSH_MB, 0)
    if streak_active:
        total_mb += await settings.get_int(SiteSettingKey.SITE_REWARD_STREAK_MB, 0)

    return total_mb * _MB


def streak_is_active(device: SiteDevice, streak_days: int) -> bool:
    """Whether the device's daily-claim streak has reached the qualifying length."""
    return streak_days > 0 and device.streak_count >= streak_days


def next_streak_count(
    prev_count: int, last_claim_at: datetime | None, now: datetime, trial_hours: int
) -> int:
    """The streak length AFTER a fresh claim happening ``now``.

    The streak counts CONSECUTIVE daily config claims. A claim is only allowed once per rolling
    ``trial_hours`` window, so a new claim that lands within one extra window of grace continues the
    streak (+1); a longer gap means a skipped day and the streak restarts at 1. The first-ever claim
    (no prior ``last_claim_at``) starts the streak at 1. Because a lapse resets on the very next
    claim — the only moment the bonus is actually provisioned — a streak can never linger stale.
    """
    if last_claim_at is None:
        return 1
    last = last_claim_at if last_claim_at.tzinfo else last_claim_at.replace(tzinfo=UTC)
    grace = timedelta(hours=max(trial_hours, 1) * 2)
    if now - last <= grace:
        return max(prev_count, 0) + 1
    return 1


async def site_device_allowance_bytes(
    settings: SettingsService, device: SiteDevice, reward_repo: SiteRewardRepository
) -> int:
    """A device's FULL current daily allowance: base + capped referral bonus + its claimed one-time
    rewards (PWA / notifications) + the streak bonus while its streak qualifies. The single source
    reused by claim provisioning, the status quote, and the referral/reward live-bump — so all four
    always agree."""
    rewards = await reward_repo.types_for_device(device.uuid)
    streak_days = await settings.get_int(SiteSettingKey.SITE_STREAK_DAYS, 0)
    return await site_compute_traffic_bytes(
        settings,
        device.referral_count,
        rewards=rewards,
        streak_active=streak_is_active(device, streak_days),
    )
