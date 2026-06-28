"""Content service — Redis-cached, token-rendered user-facing copy.

Reads from Redis, falls back to the DB (ContentRepository), then caches. Renders ``{token}``
placeholders by substituting only the provided tokens (any other ``{...}`` is left intact) — never
``str.replace`` on message text.
"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass

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


@dataclass(frozen=True, slots=True)
class RenderedMessage:
    """A rendered content body plus whether Telegram should show its link preview."""

    text: str
    link_preview: bool


class ContentService:
    def __init__(self, session: AsyncSession, redis: Redis) -> None:
        self._repo = ContentRepository(session)
        self._redis = redis

    async def _row(self, key: str, lang: Language) -> tuple[str, bool] | None:
        """The (body, link_preview) for a (key, language), Redis-cached as a small JSON blob."""
        ck = content_key(lang.value, key)
        cached = await self._redis.get(ck)
        if cached is not None:
            try:
                data = json.loads(cached)
            except (json.JSONDecodeError, TypeError):
                return cached, True  # legacy plain-string cache entry (pre link_preview)
            if isinstance(data, dict) and "b" in data:
                return data["b"], bool(data.get("lp", True))
            return cached, True
        row = await self._repo.get_message(key, lang)
        if row is not None:
            blob = json.dumps({"b": row[0], "lp": row[1]}, ensure_ascii=False)
            await self._redis.set(ck, blob, ex=CACHE_TTL)
        return row

    async def message(self, key: str, lang: Language, **tokens: object) -> RenderedMessage:
        """The rendered body + its link-preview flag (Farsi fallback like ``text``)."""
        row = await self._row(key, lang)
        if row is None and lang is not _FALLBACK_LANG:
            row = await self._row(key, _FALLBACK_LANG)
        if row is None:
            logger.warning("content missing: key=%s lang=%s", key, lang.value)
            return RenderedMessage(f"[{key}]", True)
        return RenderedMessage(render(row[0], tokens), row[1])

    async def text(self, key: str, lang: Language, **tokens: object) -> str:
        return (await self.message(key, lang, **tokens)).text

    async def set(self, key: str, lang: Language, body: str, link_preview: bool = True) -> None:
        """Admin edit (Phase 7): upsert the row and invalidate its cache entry."""
        await self._repo.upsert(key, lang, body, link_preview)
        await self._redis.delete(content_key(lang.value, key))
