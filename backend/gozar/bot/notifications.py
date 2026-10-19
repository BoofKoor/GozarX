"""Post-commit notification buffer.

Handlers QUEUE user-facing sends here instead of calling the bot inline; the context middleware
flushes them only AFTER the per-update commit succeeds, so nothing a user sees can precede a durable
write (a referral "+1" must be committed before the inviter is told about it). Each queued send is
isolated — one blocked/transient failure never blocks the others, nor the commit.
"""

from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable
from typing import Any

from aiogram import Bot
from aiogram.exceptions import TelegramBadRequest
from aiogram.types import InlineKeyboardMarkup, Message

from gozar.bot.replies import preview_options

logger = logging.getLogger("gozar.bot.notifications")


def _is_not_modified(exc: TelegramBadRequest) -> bool:
    return "not modified" in str(exc).lower()


class PendingNotifications:
    def __init__(self) -> None:
        self._actions: list[Callable[[Bot | None], Awaitable[Any]]] = []

    def send(
        self,
        chat_id: int,
        text: str,
        reply_markup: InlineKeyboardMarkup | None = None,
        *,
        link_preview: bool = True,
    ) -> None:
        """Queue a fresh message to an arbitrary chat (e.g. the inviter)."""

        async def action(bot: Bot | None) -> None:
            if bot is not None:  # bot disabled in dev (no token) — nothing to send
                await bot.send_message(
                    chat_id,
                    text,
                    reply_markup=reply_markup,
                    link_preview_options=preview_options(link_preview),
                )

        self._actions.append(action)

    def edit(
        self,
        message: Message,
        text: str,
        reply_markup: InlineKeyboardMarkup | None = None,
        *,
        link_preview: bool = True,
        fallback_reply_markup: InlineKeyboardMarkup | None = None,
        fallback_text: str | None = None,
        on_fallback: Callable[[str], Awaitable[None]] | None = None,
    ) -> None:
        """Queue an edit of the triggering message (uses the message's bound bot).

        The fallbacks are the message WITHOUT custom emoji — the premium location flags in the
        text, the flag icons and the ad button's icon on the keyboard. Telegram refuses a whole
        message over one emoji it won't take (a stale id, a bot owner without Premium), so when
        the edit is refused it is retried once as the fallback: a premium flag must never cost a
        user their delivered config. ``on_fallback(reason)`` hears that the fallback was needed
        (the look then draws plain emoji for a while)."""

        async def action(_bot: Bot | None) -> None:
            options = preview_options(link_preview)
            try:
                await message.edit_text(
                    text, reply_markup=reply_markup, link_preview_options=options
                )
            except TelegramBadRequest as exc:
                plain_text = fallback_text if fallback_text is not None else text
                plain_markup = fallback_reply_markup or reply_markup
                themed = fallback_text is not None or fallback_reply_markup is not None
                if not themed or _is_not_modified(exc):
                    raise
                logger.warning("custom emoji refused (%s); sending the message plain", exc)
                await message.edit_text(
                    plain_text, reply_markup=plain_markup, link_preview_options=options
                )
                if on_fallback is not None:
                    await on_fallback(str(exc))

        self._actions.append(action)

    async def flush(self, bot: Bot | None) -> None:
        for action in self._actions:
            try:
                await action(bot)
            except Exception:  # blocked user / transient — best-effort, never fail the update
                logger.warning("pending notification send failed (ignored)")
        self._actions.clear()
