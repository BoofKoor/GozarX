"""The console's appearance: the 🎨 switches, and what Telegram taught us about premium emoji.

The switches (premium icons, rich messages) are runtime config, so they live in the ``settings``
table (Redis-cached by ``SettingsService``) and are flipped from 🎨 in the bot. What Telegram taught
us is Redis-only and shared by the app and the worker, because both draw screens:

* ``LOOK_BLOCKED_KEY`` — Telegram refused or dropped our custom emoji (the bot's owner has no
  Premium). Plain emoji for a day, then the next screen tries again — the subscription may be back
  — or at once from 🎨. The value is Telegram's reason, shown in 🎨.
* ``LOOK_MISSING_KEY`` — ids the daily ``getCustomEmojiStickers`` check (``verify_premium_emoji``
  in the worker) found Telegram no longer knows; drawn as the plain emoji.
* ``LOOK_NOTICE_KEY`` — a one-time note for the console home when a block starts.

A Redis failure reads as "nothing learned": the screen is drawn with the switches alone, and the
sender's fallback still keeps it from failing.
"""

from __future__ import annotations

import json
import logging
import time

from redis.asyncio import Redis

from gozar.services.settings_service import SettingKey, SettingsService
from gozar.ui.look import Look

logger = logging.getLogger("gozar.services.look")

LOOK_BLOCKED_KEY = "look:premium_blocked"
LOOK_MISSING_KEY = "look:emoji_missing"
LOOK_NOTICE_KEY = "look:notice"
#: How long plain emoji are drawn after Telegram refused ours.
BLOCK_TTL = 24 * 3600
#: The daily check rewrites the missing list; past two days without one it is dropped.
MISSING_TTL = 2 * 24 * 3600
NOTICE_TTL = 7 * 24 * 3600


class LookService:
    def __init__(self, settings: SettingsService | None, redis: Redis) -> None:
        self._settings = settings
        self._redis = redis

    async def snapshot(self) -> Look:
        """What the next screen is drawn with."""
        premium = rich = True
        if self._settings is not None:
            premium = await self._settings.get_bool(SettingKey.LOOK_PREMIUM, True)
            rich = await self._settings.get_bool(SettingKey.LOOK_RICH, True)
        blocked = False
        missing: frozenset[str] = frozenset()
        try:
            blocked = bool(await self._redis.exists(LOOK_BLOCKED_KEY))
            raw = await self._redis.get(LOOK_MISSING_KEY)
            if raw:
                missing = frozenset(str(x) for x in json.loads(raw).get("ids", []))
        except Exception:  # noqa: BLE001 — nothing learned is a safe answer
            logger.warning("look: could not read the learned state")
        return Look(premium=premium, rich=rich, blocked=blocked, missing=missing)

    async def set_switch(self, key: str, on: bool) -> None:
        if self._settings is None:
            raise RuntimeError("look switches need the settings service")
        await self._settings.set(key, "true" if on else "false")

    # ---- what Telegram told us -----------------------------------------------------------------
    async def refused(self, reason: str) -> None:
        """Telegram refused or dropped our custom emoji: plain emoji for ``BLOCK_TTL``."""
        try:
            first = await self._redis.set(LOOK_BLOCKED_KEY, reason[:300], ex=BLOCK_TTL, nx=True)
            if first:
                logger.warning("premium emoji not accepted (%s): drawing plain emoji", reason)
                await self._redis.set(LOOK_NOTICE_KEY, "blocked", ex=NOTICE_TTL)
        except Exception:  # noqa: BLE001
            logger.warning("look: could not record the premium refusal")

    async def kept(self) -> None:
        """Telegram kept our custom emoji: whatever blocked them is over."""
        try:
            if await self._redis.delete(LOOK_BLOCKED_KEY):
                logger.info("premium emoji: Telegram keeps them again")
        except Exception:  # noqa: BLE001
            logger.warning("look: could not clear the premium block")

    async def retry(self) -> None:
        """🎨 "try again": drop the block now rather than at its expiry."""
        await self._redis.delete(LOOK_BLOCKED_KEY, LOOK_NOTICE_KEY)

    async def blocked_reason(self) -> str | None:
        try:
            return await self._redis.get(LOOK_BLOCKED_KEY)
        except Exception:  # noqa: BLE001
            return None

    async def take_notice(self) -> str | None:
        """The one-time note for the console home ("blocked"), consumed by reading it."""
        try:
            return await self._redis.getdel(LOOK_NOTICE_KEY)
        except Exception:  # noqa: BLE001
            return None

    async def record_missing(self, missing: set[str]) -> None:
        """The daily check's answer: the ids Telegram no longer knows (empty = all known)."""
        payload = json.dumps({"ids": sorted(missing), "at": time.time()})
        await self._redis.set(LOOK_MISSING_KEY, payload, ex=MISSING_TTL)

    async def checked(self) -> tuple[float, int] | None:
        """``(when, how many missing)`` of the last daily check, or None if none is recorded."""
        try:
            raw = await self._redis.get(LOOK_MISSING_KEY)
            if not raw:
                return None
            data = json.loads(raw)
            return float(data.get("at", 0)), len(data.get("ids", []))
        except Exception:  # noqa: BLE001
            return None
