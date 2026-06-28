"""Main-menu navigation. All feature screens are live (config/status/invite/settings)."""

from __future__ import annotations

from aiogram import F, Router
from aiogram.types import CallbackQuery, Message

from gozar.bot import callbacks as cb
from gozar.bot.keyboards import back_keyboard, help_keyboard, main_menu_keyboard
from gozar.bot.replies import answer_message, edit_message
from gozar.db.models.user import User
from gozar.services.content import ContentService
from gozar.ui.buttons import ButtonOverrides

router = Router(name="menu")


@router.callback_query(F.data == cb.MENU_HOME)
async def menu_home(
    callback: CallbackQuery, user: User, content: ContentService, buttons: ButtonOverrides
) -> None:
    await callback.answer()
    msg = await content.message("main_menu", user.language)
    if isinstance(callback.message, Message):
        await edit_message(callback.message, msg, main_menu_keyboard(user.language, buttons))


@router.callback_query(F.data == cb.MENU_HOME_NEW)
async def menu_home_new(
    callback: CallbackQuery, user: User, content: ContentService, buttons: ButtonOverrides
) -> None:
    """Deliver-screen 'show main menu' — a NEW message, so the delivered config stays in chat."""
    await callback.answer()
    msg = await content.message("main_menu", user.language)
    if isinstance(callback.message, Message):
        await answer_message(callback.message, msg, main_menu_keyboard(user.language, buttons))


@router.callback_query(F.data == cb.MENU_HELP)
async def menu_help(
    callback: CallbackQuery, user: User, content: ContentService, buttons: ButtonOverrides
) -> None:
    await callback.answer()
    msg = await content.message("help", user.language)
    if isinstance(callback.message, Message):
        await edit_message(callback.message, msg, help_keyboard(user.language, buttons))


@router.callback_query(F.data == cb.MENU_APPS)
async def menu_apps(
    callback: CallbackQuery, user: User, content: ContentService, buttons: ButtonOverrides
) -> None:
    """Required-apps info screen (from the get-config picker) — often holds download links."""
    await callback.answer()
    msg = await content.message("required_apps", user.language)
    if isinstance(callback.message, Message):
        await edit_message(callback.message, msg, back_keyboard(user.language, buttons))
