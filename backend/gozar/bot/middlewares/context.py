"""Single-AsyncSession-per-update middleware.

Opens one session per update, loads/creates the user, and injects the user + repos + services into
the handler ``data``. Gates banned users and owns the transaction (commit on success, rollback on
error; repositories only flush). Handlers never open their own session nor re-query the same user.
"""

from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable
from typing import Any

from aiogram import BaseMiddleware
from aiogram.types import CallbackQuery, Message, TelegramObject
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import async_sessionmaker

from gozar.db.models.enums import UserStatus
from gozar.db.models.user import User
from gozar.db.repositories.config_log import ConfigLogRepository
from gozar.db.repositories.user import UserRepository
from gozar.remnawave import RemnawaveClient
from gozar.services.content import ContentService
from gozar.services.settings_service import SettingsService

logger = logging.getLogger("gozar.bot.middleware")

Handler = Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]]


class ContextMiddleware(BaseMiddleware):
    def __init__(
        self, sessionmaker: async_sessionmaker, redis: Redis, panel: RemnawaveClient
    ) -> None:
        self._sessionmaker = sessionmaker
        self._redis = redis
        self._panel = panel

    async def __call__(self, handler: Handler, event: TelegramObject, data: dict[str, Any]) -> Any:
        tg_user = getattr(event, "from_user", None)
        if tg_user is None:  # events without a user (e.g. channel posts) — pass through untouched
            return await handler(event, data)

        async with self._sessionmaker() as session:
            user_repo = UserRepository(session)
            user, created = await user_repo.get_or_create(tg_user.id)
            content = ContentService(session, self._redis)
            data.update(
                session=session,
                user=user,
                created=created,
                content=content,
                settings=SettingsService(session, self._redis),
                user_repo=user_repo,
                config_log_repo=ConfigLogRepository(session),
                panel=self._panel,
            )
            if user.status is UserStatus.banned:
                await _notify_banned(event, content, user)
                await session.commit()
                return None
            result = await handler(event, data)
            await session.commit()
            return result


async def _notify_banned(event: TelegramObject, content: ContentService, user: User) -> None:
    text = await content.text("banned", user.language)
    if isinstance(event, CallbackQuery):
        await event.answer()
        if event.message:
            await event.message.answer(text)
    elif isinstance(event, Message):
        await event.answer(text)
