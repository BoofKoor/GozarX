"""Build the aiogram Bot + Dispatcher for webhook delivery.

Redis-backed FSM storage keyed with an ``fsm`` prefix so it never collides with the content/settings
cache (``cache:``) or the arq queue. The single-session-per-update middleware is registered as outer
middleware on both message and callback_query.
"""

from __future__ import annotations

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.base import DefaultKeyBuilder
from aiogram.fsm.storage.redis import RedisStorage
from arq import ArqRedis
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import async_sessionmaker

from gozar.bot.errors import register_error_handler
from gozar.bot.handlers import register_handlers
from gozar.bot.middlewares import ContextMiddleware
from gozar.remnawave import RemnawaveClient


def build_bot(token: str) -> Bot:
    return Bot(token, default=DefaultBotProperties(parse_mode=ParseMode.HTML))


def build_dispatcher(
    sessionmaker: async_sessionmaker,
    redis: Redis,
    panel: RemnawaveClient,
    arq: ArqRedis | None = None,
) -> Dispatcher:
    storage = RedisStorage(redis, key_builder=DefaultKeyBuilder(prefix="fsm"))
    dp = Dispatcher(storage=storage)
    middleware = ContextMiddleware(sessionmaker, redis, panel, arq)
    dp.message.outer_middleware(middleware)
    dp.callback_query.outer_middleware(middleware)
    register_handlers(dp)
    register_error_handler(dp)
    return dp
