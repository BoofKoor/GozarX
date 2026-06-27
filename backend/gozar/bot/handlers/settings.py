"""User settings: a language picker + a reminder sub-screen (v1's two-level layout).

These edit the user's own message inline (no commit-sensitive cross-user side-effect), so they keep
the simple inline pattern rather than the post-commit notification buffer.
"""

from __future__ import annotations

from aiogram import F, Router
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, Message

from gozar.bot import callbacks as cb
from gozar.bot.keyboards import language_keyboard, reminder_keyboard, settings_keyboard
from gozar.db.models.user import User
from gozar.services.content import ContentService
from gozar.ui.buttons import ButtonOverrides

router = Router(name="settings")


async def _edit(callback: CallbackQuery, text: str, markup: InlineKeyboardMarkup) -> None:
    if isinstance(callback.message, Message):
        await callback.message.edit_text(text, reply_markup=markup)


@router.callback_query(F.data == cb.MENU_SETTINGS)
async def open_settings(
    callback: CallbackQuery, user: User, content: ContentService, buttons: ButtonOverrides
) -> None:
    await callback.answer()
    text = await content.text("settings_menu", user.language)
    await _edit(callback, text, settings_keyboard(user.language, buttons))


@router.callback_query(F.data == cb.SETTINGS_LANGUAGE)
async def choose_language(callback: CallbackQuery, user: User, content: ContentService) -> None:
    await callback.answer()
    # The language picker reuses the start.py `lang:set:` callback (lands on the main menu).
    text = await content.text("choose_language", user.language)
    await _edit(callback, text, language_keyboard())


@router.callback_query(F.data == cb.SETTINGS_REMINDER)
async def reminder_settings(
    callback: CallbackQuery, user: User, content: ContentService, buttons: ButtonOverrides
) -> None:
    await callback.answer()
    text = await content.text("reminder_setting", user.language)
    markup = reminder_keyboard(
        user.language, reminder_enabled=user.reminder_enabled, buttons=buttons
    )
    await _edit(callback, text, markup)


async def _apply_reminder(
    callback: CallbackQuery,
    user: User,
    content: ContentService,
    buttons: ButtonOverrides,
    *,
    enabled: bool,
) -> None:
    user.reminder_enabled = enabled  # persisted on the middleware commit
    await callback.answer()
    text = await content.text("reminder_status", user.language)
    markup = reminder_keyboard(user.language, reminder_enabled=enabled, buttons=buttons)
    await _edit(callback, text, markup)


@router.callback_query(F.data == cb.SETTINGS_REMINDER_ON)
async def set_reminder_on(
    callback: CallbackQuery, user: User, content: ContentService, buttons: ButtonOverrides
) -> None:
    await _apply_reminder(callback, user, content, buttons, enabled=True)


@router.callback_query(F.data == cb.SETTINGS_REMINDER_OFF)
async def set_reminder_off(
    callback: CallbackQuery, user: User, content: ContentService, buttons: ButtonOverrides
) -> None:
    await _apply_reminder(callback, user, content, buttons, enabled=False)
