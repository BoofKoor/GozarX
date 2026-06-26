"""Content + settings service integration (DB-gated; fakeredis for the cache)."""

from __future__ import annotations

import os

import fakeredis.aioredis
import pytest
import pytest_asyncio

from gozar.db.models.enums import Language
from gozar.db.repositories.content import ContentRepository
from gozar.db.repositories.settings import SettingsRepository
from gozar.services.content import ContentService
from gozar.services.settings_service import SettingsService

pytestmark = pytest.mark.skipif(
    not os.environ.get("TEST_DATABASE_URL"), reason="TEST_DATABASE_URL not set"
)


@pytest_asyncio.fixture
async def redis():
    client = fakeredis.aioredis.FakeRedis(decode_responses=True)
    yield client
    await client.aclose()


async def test_content_cache_miss_then_hit_and_fallback(session, redis) -> None:
    await ContentRepository(session).add_default("welcome", Language.fa, "سلام {name}")
    await session.commit()
    svc = ContentService(session, redis)

    assert await svc.text("welcome", Language.fa, name="Ali") == "سلام Ali"  # miss -> DB -> render
    assert await redis.get("cache:content:fa:welcome") == "سلام {name}"  # now cached
    assert await svc.text("welcome", Language.en, name="Bob") == "سلام Bob"  # en missing -> fa
    assert await svc.text("nope", Language.en) == "[nope]"  # truly missing


async def test_settings_cache_and_invalidation(session, redis) -> None:
    await SettingsRepository(session).add_default("daily_limit_mb", "1024")
    await session.commit()
    svc = SettingsService(session, redis)
    assert await svc.get_int("daily_limit_mb") == 1024

    await svc.set("daily_limit_mb", "2048")  # invalidates the cached dict
    await session.commit()
    assert await svc.get_int("daily_limit_mb") == 2048


async def test_add_default_is_non_clobbering(session) -> None:
    repo = SettingsRepository(session)
    await repo.add_default("k", "first")
    await session.commit()
    await repo.set("k", "edited")  # admin edit
    await session.commit()
    await repo.add_default("k", "first")  # seed re-run on next boot
    await session.commit()
    assert await repo.get("k") == "edited"  # preserved
