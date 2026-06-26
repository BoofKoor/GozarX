"""/start command + language selection."""

from __future__ import annotations

from aiogram import F, Router
from aiogram.filters import CommandObject, CommandStart
from aiogram.types import CallbackQuery, Message

from gozar.bot import callbacks as cb
from gozar.bot.keyboards import language_keyboard, main_menu_keyboard
from gozar.db.models.enums import Language
from gozar.db.models.user import User
from gozar.services.content import ContentService

router = Router(name="start")


def _parse_referrer(args: str | None, self_id: int) -> int | None:
    if not args:
        return None
    try:
        referrer = int(args)
    except ValueError:
        return None
    return referrer if referrer != self_id else None


@router.message(CommandStart())
async def cmd_start(
    message: Message,
    command: CommandObject,
    user: User,
    created: bool,
    content: ContentService,
) -> None:
    if created:
        referrer = _parse_referrer(command.args, self_id=user.telegram_id)
        if referrer is not None:
            # Record the inviter now; the +1 count / reward / notify is Phase 5.
            user.referred_by = referrer
        text = await content.text("choose_language", user.language)
        await message.answer(text, reply_markup=language_keyboard())
    else:
        text = await content.text("main_menu", user.language)
        await message.answer(text, reply_markup=main_menu_keyboard(user.language))


@router.callback_query(F.data.startswith(cb.LANG_PREFIX))
async def set_language(callback: CallbackQuery, user: User, content: ContentService) -> None:
    code = (callback.data or "").removeprefix(cb.LANG_PREFIX)
    try:
        lang = Language(code)
    except ValueError:
        await callback.answer()
        return
    user.language = lang  # persisted on commit
    await callback.answer()
    text = await content.text("welcome", lang)
    if isinstance(callback.message, Message):
        await callback.message.edit_text(text, reply_markup=main_menu_keyboard(lang))
