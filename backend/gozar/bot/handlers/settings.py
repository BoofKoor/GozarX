"""User settings: change language + toggle the expiry/limit reminders.

These edit the user's own message inline (no commit-sensitive cross-user side-effect), so they keep
the simple inline pattern rather than the post-commit notification buffer.
"""

from __future__ import annotations

from aiogram import F, Router
from aiogram.types import CallbackQuery, Message

from gozar.bot import callbacks as cb
from gozar.bot.i18n import t
from gozar.bot.keyboards import language_keyboard, settings_keyboard
from gozar.db.models.user import User
from gozar.services.content import ContentService

router = Router(name="settings")


async def _show(callback: CallbackQuery, user: User, content: ContentService) -> None:
    text = await content.text("settings_menu", user.language)
    if isinstance(callback.message, Message):
        await callback.message.edit_text(
            text,
            reply_markup=settings_keyboard(user.language, reminder_enabled=user.reminder_enabled),
        )


@router.callback_query(F.data == cb.MENU_SETTINGS)
async def open_settings(callback: CallbackQuery, user: User, content: ContentService) -> None:
    await callback.answer()
    await _show(callback, user, content)


@router.callback_query(F.data == cb.SETTINGS_REMINDER_TOGGLE)
async def toggle_reminder(callback: CallbackQuery, user: User, content: ContentService) -> None:
    user.reminder_enabled = not user.reminder_enabled  # persisted on the middleware commit
    toast = t("reminder_on" if user.reminder_enabled else "reminder_off", user.language)
    await callback.answer(toast)
    await _show(callback, user, content)


@router.callback_query(F.data == cb.SETTINGS_LANG)
async def choose_language(callback: CallbackQuery, user: User, content: ContentService) -> None:
    await callback.answer()
    text = await content.text("choose_language", user.language)
    if isinstance(callback.message, Message):
        # The language picker reuses the start.py `lang:set:` callback (lands on the main menu).
        await callback.message.edit_text(text, reply_markup=language_keyboard())
