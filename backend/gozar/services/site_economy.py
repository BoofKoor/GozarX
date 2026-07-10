"""Website trial economics — the site's quota math, driven entirely by the ``site_*`` settings.

The site analogue of ``trial.compute_traffic_bytes``: it reads the ``site_*`` keys (NOT the bot's),
so the two economies are fully independent. This is the single source of the site quota — reused by
site claim flow (P3), the referral live-bump (P5), and the status "next allowance" quote (P4). Never
hardcodes a reward/cap; every number comes from settings.
"""

from __future__ import annotations

from collections.abc import Collection

from gozar.db.models.site_reward import SiteRewardType
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
