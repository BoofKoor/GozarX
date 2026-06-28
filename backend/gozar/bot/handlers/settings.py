"""User settings: a language picker + a one-tap reminder toggle.

These edit the user's own message inline (no commit-sensitive cross-user side-effect), so they keep
the simple inline pattern rather than the post-commit notification buffer.
"""

from __future__ import annotations

from aiogram import F, Router
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, Message

from gozar.bot import callbacks as cb
from gozar.bot.keyboards import language_keyboard, settings_keyboard
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
    markup = settings_keyboard(
        user.language, reminder_enabled=user.reminder_enabled, buttons=buttons
    )
    await _edit(callback, text, markup)


@router.callback_query(F.data == cb.SETTINGS_LANGUAGE)
async def choose_language(callback: CallbackQuery, user: User, content: ContentService) -> None:
    await callback.answer()
    # The language picker reuses the start.py `lang:set:` callback (lands on the main menu).
    text = await content.text("choose_language", user.language)
    await _edit(callback, text, language_keyboard())


@router.callback_query(F.data == cb.SETTINGS_REMINDER_TOGGLE)
async def toggle_reminder(
    callback: CallbackQuery, user: User, content: ContentService, buttons: ButtonOverrides
) -> None:
    """Flip reminder_enabled (persisted on the middleware commit), pop a toast with the new state,
    and re-render just the keyboard in place so the toggle label flips."""
    user.reminder_enabled = not user.reminder_enabled
    toast_key = "reminder_enabled" if user.reminder_enabled else "reminder_disabled"
    await callback.answer(await content.text(toast_key, user.language), show_alert=False)
    if isinstance(callback.message, Message):
        markup = settings_keyboard(
            user.language, reminder_enabled=user.reminder_enabled, buttons=buttons
        )
        await callback.message.edit_reply_markup(reply_markup=markup)
