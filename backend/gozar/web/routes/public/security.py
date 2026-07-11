"""Public-endpoint guards: Cloudflare Turnstile verification + a Redis fixed-window rate limit.

Both are single, bounded operations (never retry loops). Turnstile is skipped when unconfigured
(dev/build) and fails CLOSED on a transient error. The rate limiter always sets a TTL — the shared
Redis db0 has no eviction, so an un-expired key would leak.
"""

from __future__ import annotations

import logging

import httpx
from redis.asyncio import Redis

from gozar.cache.redis import site_ratelimit_key
from gozar.config.settings import get_settings

logger = logging.getLogger("gozar.web.public")

_TURNSTILE_URL = "https://challenges.cloudflare.com/turnstile/v0/siteverify"


async def verify_turnstile(client: httpx.AsyncClient, token: str, remote_ip: str) -> bool:
    """Verify a Turnstile token server-side. Returns True when unconfigured (dev), else the panel
    verdict; a single bounded call, failing CLOSED (False) on any transient/parse error."""
    secret = get_settings().turnstile_secret.get_secret_value()
    if not secret:
        return True  # not configured — dev/build; the endpoint's rate limit still applies.
    if not token:
        return False
    try:
        resp = await client.post(
            _TURNSTILE_URL,
            data={"secret": secret, "response": token, "remoteip": remote_ip},
            timeout=httpx.Timeout(8.0),
        )
        data = resp.json()
    except (httpx.HTTPError, ValueError):
        logger.warning("turnstile verification failed (transient) — treating as unverified")
        return False
    return bool(data.get("success"))


async def rate_limit_ok(
    redis: Redis, bucket: str, identifier: str, *, limit: int, window_seconds: int
) -> bool:
    """Fixed-window limiter: allow up to ``limit`` hits per ``window_seconds`` for
    ``(bucket, identifier)``. Returns True while under the limit. The counter ALWAYS gets a TTL.

    The window's TTL is stamped atomically at creation via ``SET NX EX`` (a single command), so the
    key can never exist without an expiry — a plain ``INCR`` + separate ``EXPIRE`` could leave a
    TTL-less counter if the process died between the two, permanently throttling that identifier in
    the eviction-less shared db0. ``SET NX`` is a no-op on an existing key, so the window is fixed
    (anchored to the first hit), not sliding."""
    key = site_ratelimit_key(bucket, identifier)
    await redis.set(key, 0, ex=max(window_seconds, 1), nx=True)
    count = await redis.incr(key)
    return count <= max(limit, 1)
