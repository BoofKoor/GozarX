"""Redis pool factory + cache-key helpers. Zero import side effects (lazy connect)."""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

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


def limited_notified_key(telegram_id: int) -> str:
    """One-shot guard for the data-limit ('invite to revive') nudge. A data-exhausted trial keeps
    its account (status stays active_config) so a referral bump can revive it — the status
    transition no longer gates the reminder, so this key does: SET NX before sending, cleared on a
    fresh claim / expiry reset / referral revive, and TTL'd to the trial window as a safety net."""
    return f"cache:limited_notified:{telegram_id}"


# --- website (site_*) keys — a separate namespace so bot and site never collide in the shared db0.
# Every caller MUST set a TTL: Redis runs one shared db0 with no eviction.
def site_sub_cache_key(device_uuid: str) -> str:
    """Per-device trial subscription cache (picker remark->link map + expiry) — the site analogue of
    ``sub_cache_key``, keyed by device uuid instead of telegram id."""
    return f"site:sub:{device_uuid}"


def site_limited_notified_key(device_uuid: str) -> str:
    """One-shot guard for the site's data-limit push nudge (the site analogue of
    ``limited_notified_key``)."""
    return f"site:limited_notified:{device_uuid}"


def site_ratelimit_key(bucket: str, identifier: str) -> str:
    """Fixed-window rate-limit counter for a public endpoint, keyed by ``bucket`` (e.g. "claim") and
    an ``identifier`` (device uuid or IP bucket). INCR + EXPIRE; the TTL is the window."""
    return f"site:rl:{bucket}:{identifier}"


def site_transfer_key(code: str) -> str:
    """One-time device-transfer code -> source device payload. Stored SET ex=600 nx, GETDEL on
    redeem (10-minute expiry)."""
    return f"site:transfer:{code}"


@asynccontextmanager
async def single_flight(
    redis: Redis, bucket: str, identifier: str, *, ttl_seconds: int
) -> AsyncIterator[bool]:
    """Serialize concurrent operations for ``(bucket, identifier)``: yields True to the first
    holder, False to a caller arriving while it's held. The lock auto-expires after ``ttl_seconds``
    (a crashed holder can't wedge the identifier) and is released on exit.

    Guards a claim's provision: without it, a double-tap / two tabs each read the same stale
    cooldown under READ COMMITTED, both pass, and race two panel accounts + a double credit. Redis
    ``SET NX`` is atomic, so exactly one caller wins the window. Infra-level (no delivery imports),
    so both the site endpoint and the bot's ``TrialService`` can reuse it."""
    key = f"lock:{bucket}:{identifier}"
    acquired = bool(await redis.set(key, 1, ex=max(ttl_seconds, 1), nx=True))
    try:
        yield acquired
    finally:
        if acquired:
            await redis.delete(key)
