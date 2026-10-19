"""The console's screen in one admin chat: drawn with the 🎨 look, kept to ONE live message.

- A button edits the message it was pressed on; a typed answer edits the live screen (whose id is
  in Redis, ``bot/screens.ScreenStore``) — so a whole flow happens in one message.
- What the admin types is deleted once its handler has read it (``consume``), so the chat holds the
  screen and nothing else. The one exception is a broadcast's source message: the worker copies it
  to every user, so it must stay until the send is over.
- ``/admin`` opens a fresh screen at the bottom and deletes the previous one.

``ConsoleMiddleware`` builds a ``Console`` per update for the owner-gated admin router, so handlers
take ``console`` like any other dependency.
"""

from __future__ import annotations

import contextlib
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any

from aiogram import BaseMiddleware, Bot
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, Message, TelegramObject

from gozar.bot import screens
from gozar.bot.screens import Content, ScreenStore
from gozar.db.models.enums import Language
from gozar.db.models.user import User
from gozar.services.look import LookService
from gozar.ui.buttons import ButtonOverrides, ButtonSpec, render_rows
from gozar.ui.look import Look
from gozar.ui.rich import Doc


@dataclass
class Console:
    bot: Bot
    chat_id: int
    lang: Language
    look: Look
    looks: LookService
    store: ScreenStore

    @property
    def rtl(self) -> bool:
        return self.lang is Language.fa

    async def show(
        self,
        content: Content,
        markup: InlineKeyboardMarkup | None = None,
        *,
        at: object = None,
        new: bool = False,
    ) -> Message | None:
        """Put ``content`` on the live screen: the message ``at`` (the one a button was pressed on),
        else the stored live screen, else a new message. ``new`` sends a fresh screen at the bottom
        and deletes the previous live one."""
        kw = {"look": self.look, "looks": self.looks, "rtl": self.rtl}
        previous = await self.store.get(self.chat_id)
        target = at.message_id if isinstance(at, Message) else (None if new else previous)
        if new or target is None:
            sent = await screens.send(self.bot, self.chat_id, content, markup, **kw)
            await self.store.put(self.chat_id, sent.message_id)
            await self._drop_stale(previous, keep=sent.message_id)
            return sent
        shown = await screens.edit(self.bot, self.chat_id, target, content, markup, **kw)
        current = shown.message_id if shown is not None else target
        await self.store.put(self.chat_id, current)
        # a button pressed on an OLDER screen makes that one live: the one that was live is stale
        await self._drop_stale(previous, keep=current, also=target)
        return shown

    async def _drop_stale(
        self, previous: int | None, *, keep: int, also: int | None = None
    ) -> None:
        if previous is not None and previous not in (keep, also):
            with contextlib.suppress(Exception):
                await self.bot.delete_message(self.chat_id, previous)

    async def send(self, content: Content, markup: InlineKeyboardMarkup | None = None) -> Message:
        """A message BESIDE the live screen (a sample, a record) — it does not become the screen."""
        return await screens.send(
            self.bot, self.chat_id, content, markup, look=self.look, looks=self.looks, rtl=self.rtl
        )

    async def consume(self, message: Message) -> None:
        """Delete what the admin typed, now that it has been read."""
        with contextlib.suppress(Exception):
            await message.delete()

    async def close(self, at: object = None) -> None:
        """Remove the screen (❌): the message and the live-screen pointer."""
        target = at.message_id if isinstance(at, Message) else await self.store.get(self.chat_id)
        if target is not None:
            with contextlib.suppress(Exception):
                await self.bot.delete_message(self.chat_id, target)
            await self.store.drop(self.chat_id, target)


def keyboard(
    lang: Language,
    rows: list[list[tuple[str, str] | tuple[str, str, str | None]]],
    buttons: ButtonOverrides | None = None,
    *,
    back: str | None = None,
) -> InlineKeyboardMarkup:
    """A console keyboard from ``(label, callback data[, style])`` cells. ``back`` appends the
    catalogue's ``admin_back`` cell with that callback (its label stays operator-editable)."""
    structure: list[list[ButtonSpec]] = [
        [
            ButtonSpec(
                label=cell[0], callback_data=cell[1], style=cell[2] if len(cell) > 2 else None
            )
            for cell in row
        ]
        for row in rows
        if row
    ]
    if back is not None:
        structure.append([ButtonSpec(key="admin_back", callback_data=back)])
    return render_rows(lang, structure, buttons)


def doc_of(content: Content) -> Doc:
    return content if isinstance(content, Doc) else Doc().text(content)


Handler = Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]]


class ConsoleMiddleware(BaseMiddleware):
    """Injects ``console`` into the admin router's handlers (inner middleware: it runs after the
    router's owner filter, so a non-owner's update never builds one)."""

    async def __call__(self, handler: Handler, event: TelegramObject, data: dict[str, Any]) -> Any:
        bot: Bot | None = data.get("bot")
        user: User | None = data.get("user")
        looks: LookService | None = data.get("looks")
        store: ScreenStore | None = data.get("screens")
        chat_id = _chat_id(event)
        if bot is not None and user is not None and looks is not None and store is not None:
            if chat_id is not None:
                data["console"] = Console(
                    bot=bot,
                    chat_id=chat_id,
                    lang=user.language,
                    look=await looks.snapshot(),
                    looks=looks,
                    store=store,
                )
        return await handler(event, data)


def _chat_id(event: TelegramObject) -> int | None:
    if isinstance(event, Message):
        return event.chat.id
    if isinstance(event, CallbackQuery) and isinstance(event.message, Message):
        return event.message.chat.id
    if isinstance(event, CallbackQuery) and event.from_user is not None:
        return event.from_user.id
    return None
