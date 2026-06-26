"""SettingsService typed coercion — against fakeredis with the cache pre-seeded (no DB needed)."""

from __future__ import annotations

import json

import fakeredis.aioredis

from gozar.cache.redis import SETTINGS_KEY
from gozar.services.settings_service import SettingsService


async def _service(values: dict[str, str]) -> SettingsService:
    redis = fakeredis.aioredis.FakeRedis(decode_responses=True)
    await redis.set(SETTINGS_KEY, json.dumps(values))
    # session is unused on a cache hit.
    return SettingsService(session=None, redis=redis)  # type: ignore[arg-type]


async def test_get_int() -> None:
    svc = await _service({"daily_limit_mb": "1024", "bad": "x"})
    assert await svc.get_int("daily_limit_mb") == 1024
    assert await svc.get_int("bad", 5) == 5
    assert await svc.get_int("missing", 7) == 7


async def test_get_bool() -> None:
    svc = await _service({"on": "true", "off": "false", "weird": "YES"})
    assert await svc.get_bool("on") is True
    assert await svc.get_bool("off") is False
    assert await svc.get_bool("weird") is True
    assert await svc.get_bool("missing", default=True) is True


async def test_get_list() -> None:
    svc = await _service({"csv": "DE, FI ,NL", "arr": '["a", "b"]', "empty": ""})
    assert await svc.get_list("csv") == ["DE", "FI", "NL"]
    assert await svc.get_list("arr") == ["a", "b"]
    assert await svc.get_list("empty") == []
    assert await svc.get_list("missing") == []
