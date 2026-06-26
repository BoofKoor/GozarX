"""Main-menu navigation. All feature screens are live (config/status/invite/settings)."""

from __future__ import annotations

from aiogram import F, Router
from aiogram.types import CallbackQuery, Message

from gozar.bot import callbacks as cb
from gozar.bot.keyboards import back_keyboard, main_menu_keyboard
from gozar.db.models.user import User
from gozar.services.content import ContentService

router = Router(name="menu")


@router.callback_query(F.data == cb.MENU_HOME)
async def menu_home(callback: CallbackQuery, user: User, content: ContentService) -> None:
    await callback.answer()
    text = await content.text("main_menu", user.language)
    if isinstance(callback.message, Message):
        await callback.message.edit_text(text, reply_markup=main_menu_keyboard(user.language))


@router.callback_query(F.data == cb.MENU_HELP)
async def menu_help(callback: CallbackQuery, user: User, content: ContentService) -> None:
    await callback.answer()
    text = await content.text("help", user.language)
    if isinstance(callback.message, Message):
        await callback.message.edit_text(text, reply_markup=back_keyboard(user.language))
