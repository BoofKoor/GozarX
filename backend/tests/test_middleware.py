"""ContextMiddleware: one session per update, user injection, banned short-circuit (DB-gated)."""

from __future__ import annotations

import os
from types import SimpleNamespace

import fakeredis.aioredis
import pytest

from gozar.bot.middlewares.context import ContextMiddleware
from gozar.db.models.enums import Language, UserStatus
from gozar.db.models.user import User
from gozar.db.repositories.user import UserRepository

pytestmark = pytest.mark.skipif(
    not os.environ.get("TEST_DATABASE_URL"), reason="TEST_DATABASE_URL not set"
)


async def test_injects_context_and_commits(db_sessions) -> None:
    redis = fakeredis.aioredis.FakeRedis(decode_responses=True)
    mw = ContextMiddleware(db_sessions, redis, panel=None)  # type: ignore[arg-type]
    captured: dict = {}

    async def handler(event, data) -> str:
        captured.update(data)
        return "handled"

    event = SimpleNamespace(from_user=SimpleNamespace(id=4242))
    result = await mw(handler, event, {})

    assert result == "handled"
    assert isinstance(captured["user"], User) and captured["user"].telegram_id == 4242
    assert captured["created"] is True
    for key in ("session", "content", "settings", "user_repo", "config_log_repo"):
        assert key in captured
    # committed -> visible from a fresh session
    async with db_sessions() as session:
        assert await UserRepository(session).get(4242) is not None
    await redis.aclose()


async def test_banned_user_short_circuits(db_sessions) -> None:
    redis = fakeredis.aioredis.FakeRedis(decode_responses=True)
    async with db_sessions() as session:
        session.add(User(telegram_id=999, status=UserStatus.banned, language=Language.fa))
        await session.commit()

    mw = ContextMiddleware(db_sessions, redis, panel=None)  # type: ignore[arg-type]
    called = False

    async def handler(event, data) -> str:
        nonlocal called
        called = True
        return "handled"

    event = SimpleNamespace(from_user=SimpleNamespace(id=999))
    result = await mw(handler, event, {})

    assert result is None
    assert called is False
    await redis.aclose()
