"""Settings service — Redis-cached runtime config with typed accessors.

The ``settings`` table holds raw strings; type coercion lives here (never in the repo). The whole
dict is cached under one key and invalidated on write.
"""

from __future__ import annotations

import json

from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from gozar.cache.redis import CACHE_TTL, SETTINGS_KEY
from gozar.db.repositories.settings import SettingsRepository


class SettingKey:
    """Canonical setting keys (avoid stringly-typed lookups scattered across the codebase)."""

    TRIAL_SQUAD = "trial_internal_squad"
    LOCATIONS = "locations"
    DAILY_LIMIT_MB = "daily_limit_mb"
    REFERRAL_REWARD_MB = "referral_reward_mb"
    REFERRAL_REWARD_LIMIT = "referral_reward_limit"
    TRIAL_HOURS = "trial_hours"
    ADS_ENABLED = "ads_enabled"
    CONFIGS_PER_PAGE = "configs_per_page"


_TRUE = {"1", "true", "yes", "on"}


class SettingsService:
    def __init__(self, session: AsyncSession, redis: Redis) -> None:
        self._repo = SettingsRepository(session)
        self._redis = redis

    async def _all(self) -> dict[str, str]:
        cached = await self._redis.get(SETTINGS_KEY)
        if cached is not None:
            return json.loads(cached)
        data = await self._repo.all_as_dict()
        await self._redis.set(SETTINGS_KEY, json.dumps(data), ex=CACHE_TTL)
        return data

    async def get(self, key: str) -> str | None:
        return (await self._all()).get(key)

    async def get_int(self, key: str, default: int = 0) -> int:
        raw = await self.get(key)
        if raw is None or raw == "":
            return default
        try:
            return int(raw)
        except ValueError:
            return default

    async def get_bool(self, key: str, default: bool = False) -> bool:
        raw = await self.get(key)
        return raw.strip().lower() in _TRUE if raw is not None else default

    async def get_list(self, key: str) -> list[str]:
        raw = await self.get(key)
        if not raw:
            return []
        raw = raw.strip()
        if raw.startswith("["):
            try:
                value = json.loads(raw)
            except json.JSONDecodeError:
                return []
            return [str(v) for v in value] if isinstance(value, list) else []
        return [part.strip() for part in raw.split(",") if part.strip()]

    async def set(self, key: str, value: str) -> None:
        await self._repo.set(key, value)
        await self._redis.delete(SETTINGS_KEY)
