"""Sending and editing screens drawn with the 🎨 look — and keeping them from ever failing on it.

A console screen is a ``Doc`` (``ui/rich``) or an HTML string, plus an inline keyboard. ``send`` and
``edit`` try, in order, until Telegram takes one:

1. the rich message (a Doc, with rich messages on and within the limits) with premium icons,
2. the same without custom emoji,
3. the regular HTML message (in-text buttons moved to the keyboard) with premium icons,
4. the same without custom emoji.

A plain string skips the rich steps. A step without icons is only tried when icons were on.
Whenever a step with icons was refused and the same step without them went through, the icons were
the problem: Telegram's reason is recorded (``LookService.refused``) and the bot draws plain emoji
for a day. A themed message that goes through tells us too: Telegram KEEPS custom emoji only for a
bot whose owner has Premium, and silently drops them otherwise — dropped reads as refused, kept
lifts any block.

An edit Telegram refuses for a reason that is about the message itself (deleted, too old, a regular
message that cannot become a rich one) sends the screen as a new message and deletes the old one,
so a screen always arrives. "message is not modified" is not an error: nothing needed doing.

Standalone (no handlers, no dispatcher), so the worker can draw with it too. The console's live
screen per chat is ``ScreenStore`` (Redis), never process memory.
"""

from __future__ import annotations

import contextlib
import logging
from dataclasses import dataclass

from aiogram import Bot
from aiogram.exceptions import TelegramBadRequest
from aiogram.types import InlineKeyboardMarkup, InputRichMessage, Message
from redis.asyncio import Redis

from gozar.services.look import LookService
from gozar.ui.look import Look
from gozar.ui.rich import Doc
from gozar.ui.theme import theme_html, theme_markup

logger = logging.getLogger("gozar.bot.screens")

Content = Doc | str

# Telegram's words for "this message can't take this edit" — retrying another rendering of the same
# edit cannot help, so the screen goes out as a new message straight away.
_UNEDITABLE = (
    "message can't be edited",
    "message to edit not found",
    "message_id_invalid",
    "there is no text in the message to edit",
    "message can't be deleted",
)


def _not_modified(exc: TelegramBadRequest) -> bool:
    return "not modified" in str(exc).lower()


def _uneditable(exc: TelegramBadRequest) -> bool:
    text = str(exc).lower()
    return any(marker in text for marker in _UNEDITABLE)


@dataclass(frozen=True, slots=True)
class _Variant:
    rich: bool
    body: str  # rich HTML or regular HTML
    markup: object
    themed: bool  # premium icons in it
    emoji: int  # how many custom emoji its text carries


def _merge(markup: object, doc: Doc) -> object:
    """The classic rendering's keyboard: the in-text buttons first, then the screen's own."""
    extra = doc.classic_rows()
    if not extra:
        return markup
    own = list(markup.inline_keyboard) if isinstance(markup, InlineKeyboardMarkup) else []
    rows = extra + own
    return InlineKeyboardMarkup(inline_keyboard=rows)


def variants(content: Content, markup: object, look: Look) -> list[_Variant]:
    """The renderings to try, best first (see the module docstring)."""
    out: list[_Variant] = []
    icons = look.icons_on

    def add(rich: bool, body: str, kb: object) -> None:
        if icons:
            themed_body, n = theme_html(body, look.text_icon)
            themed_kb = theme_markup(kb, look.button_icon)
            if n or themed_kb is not kb:
                out.append(_Variant(rich, themed_body, themed_kb, True, n))
        out.append(_Variant(rich, body, theme_markup(kb, None), False, 0))

    if isinstance(content, Doc):
        if look.rich and content.fits_rich():
            add(True, content.rich(), markup)
        add(False, content.classic(), _merge(markup, content))
    else:
        add(False, content, markup)
    return out


def kept_custom_emoji(message: object, rich: bool) -> bool | None:
    """Did Telegram keep the custom emoji of the message it just took? None = can't tell."""
    if not isinstance(message, Message):
        return None
    if rich:
        if message.rich_message is None:
            return None
        return "custom_emoji" in message.rich_message.model_dump_json()
    if message.entities is None and message.text is None:
        return None
    return any(e.type == "custom_emoji" for e in message.entities or [])


async def _learn(looks: LookService | None, v: _Variant, result: object) -> None:
    if looks is None or not v.themed or not v.emoji:
        return
    kept = kept_custom_emoji(result, v.rich)
    if kept is True:
        await looks.kept()
    elif kept is False:
        await looks.refused("Telegram dropped the custom emoji")


def _rich(body: str, rtl: bool) -> InputRichMessage:
    return InputRichMessage(html=body, is_rtl=rtl)


async def _send_variant(bot: Bot, chat_id: int, v: _Variant, rtl: bool) -> Message:
    if v.rich:
        return await bot.send_rich_message(chat_id, _rich(v.body, rtl), reply_markup=v.markup)
    return await bot.send_message(chat_id, v.body, reply_markup=v.markup)


async def _edit_variant(
    bot: Bot, chat_id: int, message_id: int, v: _Variant, rtl: bool
) -> Message | bool:
    if v.rich:
        return await bot.edit_message_text(
            chat_id=chat_id,
            message_id=message_id,
            rich_message=_rich(v.body, rtl),
            reply_markup=v.markup,
            parse_mode=None,
            link_preview_options=None,
            disable_web_page_preview=None,
        )
    return await bot.edit_message_text(
        v.body, chat_id=chat_id, message_id=message_id, reply_markup=v.markup
    )


async def _refused_icons(
    looks: LookService | None, failed: list[tuple[_Variant, str]], v: _Variant
) -> None:
    """``v`` went through: if the same rendering WITH icons was refused, the icons were why."""
    if looks is None or v.themed:
        return
    for prev, reason in failed:
        if prev.themed and prev.rich == v.rich:
            await looks.refused(reason)
            return


async def send(
    bot: Bot,
    chat_id: int,
    content: Content,
    markup: object = None,
    *,
    look: Look,
    looks: LookService | None = None,
    rtl: bool = True,
) -> Message:
    """Send a screen as a new message (the best rendering Telegram takes)."""
    failed: list[tuple[_Variant, str]] = []
    last: TelegramBadRequest | None = None
    for v in variants(content, markup, look):
        try:
            sent = await _send_variant(bot, chat_id, v, rtl)
        except TelegramBadRequest as exc:
            logger.warning("telegram refused a %s screen: %s", "rich" if v.rich else "regular", exc)
            failed.append((v, str(exc)))
            last = exc
            continue
        await _refused_icons(looks, failed, v)
        await _learn(looks, v, sent)
        return sent
    assert last is not None
    raise last


async def edit(
    bot: Bot,
    chat_id: int,
    message_id: int,
    content: Content,
    markup: object = None,
    *,
    look: Look,
    looks: LookService | None = None,
    rtl: bool = True,
) -> Message | None:
    """Show a screen in place of message ``message_id``. Returns the message now showing it — a
    NEW one when the edit could not be made (the old one is then deleted) — or None when the
    message already showed exactly this."""
    failed: list[tuple[_Variant, str]] = []
    for v in variants(content, markup, look):
        try:
            result = await _edit_variant(bot, chat_id, message_id, v, rtl)
        except TelegramBadRequest as exc:
            if _not_modified(exc):
                return None
            failed.append((v, str(exc)))
            if _uneditable(exc):
                break
            continue
        await _refused_icons(looks, failed, v)
        await _learn(looks, v, result)
        return result if isinstance(result, Message) else None
    if failed:
        logger.info("could not edit message %s (%s); sending it anew", message_id, failed[-1][1])
    sent = await send(bot, chat_id, content, markup, look=look, looks=looks, rtl=rtl)
    with contextlib.suppress(Exception):
        await bot.delete_message(chat_id, message_id)
    return sent


# ---- the console's one live screen per chat ------------------------------------------------------
SCREEN_TTL = 30 * 24 * 3600


def _screen_key(chat_id: int) -> str:
    return f"admin:screen:{chat_id}"


class ScreenStore:
    """Which message is the console's live screen in a chat: buttons edit the message they were
    pressed on, a typed answer edits this one. In Redis, so a restart or the worker sees it too."""

    def __init__(self, redis: Redis) -> None:
        self._redis = redis

    async def get(self, chat_id: int) -> int | None:
        try:
            raw = await self._redis.get(_screen_key(chat_id))
        except Exception:  # noqa: BLE001 — no live screen: the next one is a new message
            return None
        return int(raw) if raw and str(raw).isdigit() else None

    async def put(self, chat_id: int, message_id: int) -> None:
        with contextlib.suppress(Exception):
            await self._redis.set(_screen_key(chat_id), message_id, ex=SCREEN_TTL)

    async def drop(self, chat_id: int, message_id: int | None = None) -> None:
        """Forget the live screen (only if it is still ``message_id``, when given)."""
        with contextlib.suppress(Exception):
            if message_id is None or await self.get(chat_id) == message_id:
                await self._redis.delete(_screen_key(chat_id))
