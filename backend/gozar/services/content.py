"""Content service — Redis-cached, token-rendered user-facing copy.

Reads from Redis, falls back to the DB (ContentRepository), then caches. Renders ``{token}``
placeholders by substituting only the provided tokens (any other ``{...}`` is left intact) — never
``str.replace`` on message text.
"""

from __future__ import annotations

import logging
import re

from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from gozar.cache.redis import CACHE_TTL, content_key
from gozar.db.models.enums import Language
from gozar.db.repositories.content import ContentRepository

logger = logging.getLogger("gozar.services.content")

_TOKEN = re.compile(r"\{(\w+)\}")
_FALLBACK_LANG = Language.fa


def render(body: str, tokens: dict[str, object]) -> str:
    """Replace ``{token}`` with provided values; leave unprovided placeholders untouched."""
    return _TOKEN.sub(
        lambda m: str(tokens[m.group(1)]) if m.group(1) in tokens else m.group(0), body
    )


class ContentService:
    def __init__(self, session: AsyncSession, redis: Redis) -> None:
        self._repo = ContentRepository(session)
        self._redis = redis

    async def _body(self, key: str, lang: Language) -> str | None:
        ck = content_key(lang.value, key)
        cached = await self._redis.get(ck)
        if cached is not None:
            return cached
        body = await self._repo.get_body(key, lang)
        if body is not None:
            await self._redis.set(ck, body, ex=CACHE_TTL)
        return body

    async def text(self, key: str, lang: Language, **tokens: object) -> str:
        body = await self._body(key, lang)
        if body is None and lang is not _FALLBACK_LANG:
            body = await self._body(key, _FALLBACK_LANG)
        if body is None:
            logger.warning("content missing: key=%s lang=%s", key, lang.value)
            return f"[{key}]"
        return render(body, tokens)

    async def set(self, key: str, lang: Language, body: str) -> None:
        """Admin edit (Phase 7): upsert the row and invalidate its cache entry."""
        await self._repo.upsert(key, lang, body)
        await self._redis.delete(content_key(lang.value, key))
