"""ReminderService: expiry/limit events reset the holder + clear the sub cache; others ignored.

DB-gated (real session) + fakeredis.
"""

from __future__ import annotations

import os

import fakeredis.aioredis
import pytest

from gozar.cache.redis import sub_cache_key
from gozar.db.models.enums import UserStatus
from gozar.db.models.user import User
from gozar.db.repositories.user import UserRepository
from gozar.remnawave.schemas import WebhookUserEvent
from gozar.services.reminders import ReminderService

pytestmark = pytest.mark.skipif(
    not os.environ.get("TEST_DATABASE_URL"), reason="TEST_DATABASE_URL not set"
)


def _event(name: str, username: str) -> WebhookUserEvent:
    return WebhookUserEvent.model_validate({"event": name, "data": {"username": username}})


async def _service(session):
    redis = fakeredis.aioredis.FakeRedis(decode_responses=True)
    return ReminderService(UserRepository(session), redis), redis


async def _add(session, **kw) -> User:
    user = User(**kw)
    session.add(user)
    await session.flush()
    return user


async def test_expired_resets_user_and_clears_cache(session) -> None:
    user = await _add(
        session, telegram_id=1, status=UserStatus.active_config, panel_username="g1_x"
    )
    service, redis = await _service(session)
    await redis.set(sub_cache_key(1), "cached-picker")  # a live picker cache to clear

    outcome = await service.apply_event(_event("user.expired", "g1_x"))

    assert outcome is not None
    assert outcome.content_key == "reminder_expired"
    assert user.status is UserStatus.available
    assert user.panel_username is None
    assert await redis.get(sub_cache_key(1)) is None


async def test_limited_maps_to_limited_key(session) -> None:
    user = await _add(
        session, telegram_id=2, status=UserStatus.active_config, panel_username="g2_x"
    )
    service, _ = await _service(session)

    outcome = await service.apply_event(_event("user.limited", "g2_x"))

    assert outcome.content_key == "reminder_limited"
    assert user.status is UserStatus.available


async def test_unknown_event_ignored(session) -> None:
    service, _ = await _service(session)
    assert await service.apply_event(_event("user.created", "whoever")) is None


async def test_unknown_username_ignored(session) -> None:
    service, _ = await _service(session)
    assert await service.apply_event(_event("user.expired", "nobody")) is None


async def test_banned_user_not_reset(session) -> None:
    user = await _add(session, telegram_id=3, status=UserStatus.banned, panel_username="g3_x")
    service, _ = await _service(session)

    assert await service.apply_event(_event("user.expired", "g3_x")) is None
    assert user.status is UserStatus.banned  # never un-banned
