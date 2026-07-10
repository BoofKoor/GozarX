"""``site_compute_traffic_bytes`` — the website quota math over the ``site_*`` settings.

DB-free: a ``SettingsService`` reads its whole dict from the (pre-seeded) Redis cache key, so no
session is ever touched — the fakeredis cache stands in for the settings table.
"""

from __future__ import annotations

import json
from typing import Any, cast

import fakeredis.aioredis

from gozar.cache.redis import SETTINGS_KEY
from gozar.db.models.site_reward import SiteRewardType
from gozar.services.settings_service import SettingsService, SiteSettingKey
from gozar.services.site_economy import site_compute_traffic_bytes

_MB = 1024 * 1024

_BASE = {
    SiteSettingKey.SITE_DAILY_LIMIT_MB: "1024",
    SiteSettingKey.SITE_REFERRAL_REWARD_MB: "500",
    SiteSettingKey.SITE_REFERRAL_REWARD_LIMIT: "10",
    SiteSettingKey.SITE_REWARD_PWA_MB: "200",
    SiteSettingKey.SITE_REWARD_PUSH_MB: "150",
    SiteSettingKey.SITE_REWARD_STREAK_MB: "300",
    SiteSettingKey.SITE_STREAK_DAYS: "7",
}


async def _settings(**overrides: str) -> SettingsService:
    redis = fakeredis.aioredis.FakeRedis(decode_responses=True)
    await redis.set(SETTINGS_KEY, json.dumps({**_BASE, **overrides}))
    # session is never used on the cache-hit path.
    return SettingsService(cast(Any, None), redis)


async def test_base_allowance_no_referrals() -> None:
    assert await site_compute_traffic_bytes(await _settings(), 0) == 1024 * _MB


async def test_referral_bonus_and_cap() -> None:
    settings = await _settings()
    assert await site_compute_traffic_bytes(settings, 3) == (1024 + 3 * 500) * _MB
    # 20 referrals is capped at the configured limit of 10.
    assert await site_compute_traffic_bytes(settings, 20) == (1024 + 10 * 500) * _MB


async def test_one_time_rewards_add() -> None:
    settings = await _settings()
    assert (
        await site_compute_traffic_bytes(settings, 0, rewards={SiteRewardType.pwa})
        == (1024 + 200) * _MB
    )
    assert (
        await site_compute_traffic_bytes(
            settings, 0, rewards={SiteRewardType.pwa, SiteRewardType.push}
        )
        == (1024 + 200 + 150) * _MB
    )


async def test_streak_bonus() -> None:
    assert (
        await site_compute_traffic_bytes(await _settings(), 0, streak_active=True)
        == (1024 + 300) * _MB
    )


async def test_all_bonuses_stack() -> None:
    got = await site_compute_traffic_bytes(
        await _settings(),
        5,
        rewards={SiteRewardType.pwa, SiteRewardType.push},
        streak_active=True,
    )
    assert got == (1024 + 5 * 500 + 200 + 150 + 300) * _MB


async def test_missing_settings_fall_back_safely() -> None:
    # Blank daily -> default 1024; blank reward -> 0 (so referrals add nothing).
    settings = await _settings(
        **{SiteSettingKey.SITE_DAILY_LIMIT_MB: "", SiteSettingKey.SITE_REFERRAL_REWARD_MB: ""}
    )
    assert await site_compute_traffic_bytes(settings, 5) == 1024 * _MB


async def test_negative_referral_count_is_clamped() -> None:
    assert await site_compute_traffic_bytes(await _settings(), -3) == 1024 * _MB
