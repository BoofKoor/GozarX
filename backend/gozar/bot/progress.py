"""A job's progress as ONE live console message, edited as the steps move.

The worker hands this reporter to a job (``services/ops_jobs``): every step change redraws the
message (at most every ``interval`` seconds — Telegram throttles a chat's edits), and while a step
runs a ticker redraws it every ``tick`` seconds so its clock moves. When the job ends, ``show``
draws its last screen in the same message.

A message that can no longer be edited (deleted, too old) is replaced by a new one at the bottom —
``bot/screens.edit`` does that — and the new one becomes the console's live screen. Telegram being
slow or refusing a redraw never fails the job: the work goes on and the next redraw tries again.
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
import time
from collections.abc import Awaitable, Callable

from aiogram import Bot
from aiogram.types import InlineKeyboardMarkup

from gozar.bot import ops_view, screens
from gozar.bot.screens import Content, ScreenStore
from gozar.ops.report import RUNNING, Reporter
from gozar.services.look import LookService
from gozar.ui.look import Look

logger = logging.getLogger("gozar.bot.progress")


class TelegramReporter(Reporter):
    def __init__(
        self,
        bot: Bot | None,
        chat_id: int,
        message_id: int | None,
        *,
        look: Look,
        looks: LookService | None,
        store: ScreenStore | None,
        on_change: Callable[[Reporter], Awaitable[None]] | None = None,
        interval: float = 1.5,
        tick: float = 5.0,
    ) -> None:
        super().__init__()
        self.bot = bot
        self.chat_id = chat_id
        self.message_id = message_id
        self.look = look
        self.looks = looks
        self.store = store
        self.on_change = on_change
        self.interval = interval
        self.tick = tick
        self.started = time.monotonic()
        self._last = 0.0
        self._dirty = False
        self._done = False
        self._lock = asyncio.Lock()
        self._ticker: asyncio.Task | None = None

    # ---- the engine's side --------------------------------------------------------------------
    async def changed(self) -> None:
        if self.on_change is not None:
            try:
                await self.on_change(self)
            except Exception:  # noqa: BLE001 — a bookkeeping hiccup must not stop the work
                logger.warning("ops progress checkpoint failed", exc_info=True)
        await self._draw()

    async def _draw(self, *, force: bool = False) -> None:
        if self._done:
            return
        if not force and time.monotonic() - self._last < self.interval:
            self._dirty = True
            return
        async with self._lock:
            if self._done:
                return
            self._dirty = False
            self._last = time.monotonic()
            await self._put(ops_view.progress_doc(self, self.started), None)

    async def _put(self, content: Content, markup: InlineKeyboardMarkup | None) -> None:
        if self.bot is None:
            return
        kw = {"look": self.look, "looks": self.looks}
        try:
            if self.message_id is None:
                shown = await screens.send(self.bot, self.chat_id, content, markup, **kw)
            else:
                shown = await screens.edit(
                    self.bot, self.chat_id, self.message_id, content, markup, **kw
                )
        except Exception:  # noqa: BLE001 — never fail the job over its picture
            logger.warning("could not draw ops progress in chat %s", self.chat_id, exc_info=True)
            return
        if shown is not None and shown.message_id != self.message_id:
            self.message_id = shown.message_id
            if self.store is not None:
                await self.store.put(self.chat_id, shown.message_id)

    async def _tick(self) -> None:
        while True:
            await asyncio.sleep(self.tick)
            if self._dirty or any(s.status == RUNNING for s in self.steps):
                await self._draw(force=True)

    # ---- the worker's side --------------------------------------------------------------------
    async def __aenter__(self) -> TelegramReporter:
        if self.bot is not None:
            self._ticker = asyncio.create_task(self._tick())
        return self

    async def __aexit__(self, *exc: object) -> None:
        if self._ticker is not None:
            self._ticker.cancel()
            with contextlib.suppress(asyncio.CancelledError, Exception):
                await self._ticker
            self._ticker = None

    async def show(self, content: Content, markup: InlineKeyboardMarkup | None) -> None:
        """The job's last screen, in the same message; nothing redraws over it afterwards."""
        async with self._lock:
            self._done = True
            await self._put(content, markup)
