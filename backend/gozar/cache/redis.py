"""Redis pool factory + cache-key helpers. Zero import side effects (lazy connect)."""

from __future__ import annotations

from redis.asyncio import Redis

# Safety-net TTL (seconds) layered on top of explicit invalidation.
CACHE_TTL = 300

SETTINGS_KEY = "cache:settings"
BUTTON_CONFIGS_KEY = "cache:button_configs"  # all button overrides, one JSON blob (Phase 7c)

# Capped list of per-minute system-health samples (newest first) for the monitoring page history.
HEALTH_HISTORY_KEY = "health:history"
HEALTH_HISTORY_MAX = 1440  # ~24h at one sample/minute


def create_redis_pool(url: str) -> Redis:
    """Build a Redis client (connection pool is lazy — no socket until first command)."""
    return Redis.from_url(url, decode_responses=True)


def content_key(lang: str, key: str) -> str:
    return f"cache:content:{lang}:{key}"


def sub_cache_key(telegram_id: int) -> str:
    """Per-user trial subscription cache (picker remark->link map + expiry). One source of this key
    so the trial service and the reminder webhook clear/refresh exactly the same entry."""
    return f"cache:sub:{telegram_id}"
