"""Shared reply helpers — apply a content message's per-text link-preview flag to a Telegram send.

Handlers fetch a ``RenderedMessage`` (body + ``link_preview``) and pass it here so the admin's
"show link preview?" choice (Texts editor) is honoured on edit/answer. ``None`` keeps Telegram's
default (preview shown); a disabled option hides it for that one message.
"""

from __future__ import annotations

from aiogram.types import InlineKeyboardMarkup, LinkPreviewOptions, Message

from gozar.services.content import RenderedMessage


def preview_options(link_preview: bool) -> LinkPreviewOptions | None:
    return None if link_preview else LinkPreviewOptions(is_disabled=True)


async def edit_message(
    message: Message, msg: RenderedMessage, markup: InlineKeyboardMarkup | None = None
) -> None:
    await message.edit_text(
        msg.text, reply_markup=markup, link_preview_options=preview_options(msg.link_preview)
    )


async def answer_message(
    message: Message, msg: RenderedMessage, markup: InlineKeyboardMarkup | None = None
) -> None:
    await message.answer(
        msg.text, reply_markup=markup, link_preview_options=preview_options(msg.link_preview)
    )
