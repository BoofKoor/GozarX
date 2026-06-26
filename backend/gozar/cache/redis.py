"""Redis pool factory + cache-key helpers. Zero import side effects (lazy connect)."""

from __future__ import annotations

from redis.asyncio import Redis

# Safety-net TTL (seconds) layered on top of explicit invalidation.
CACHE_TTL = 300

SETTINGS_KEY = "cache:settings"


def create_redis_pool(url: str) -> Redis:
    """Build a Redis client (connection pool is lazy — no socket until first command)."""
    return Redis.from_url(url, decode_responses=True)


def content_key(lang: str, key: str) -> str:
    return f"cache:content:{lang}:{key}"
