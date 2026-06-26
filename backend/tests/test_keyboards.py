"""Inline keyboard structure + namespaced callback data."""

from __future__ import annotations

from aiogram.types import InlineKeyboardMarkup

from gozar.bot import callbacks as cb
from gozar.bot.keyboards import back_keyboard, language_keyboard, main_menu_keyboard
from gozar.db.models.enums import Language


def _callbacks(markup: InlineKeyboardMarkup) -> list[str]:
    return [btn.callback_data for row in markup.inline_keyboard for btn in row]


def test_language_keyboard() -> None:
    assert _callbacks(language_keyboard()) == ["lang:set:fa", "lang:set:en", "lang:set:ru"]


def test_main_menu_keyboard() -> None:
    assert _callbacks(main_menu_keyboard(Language.fa)) == [
        cb.MENU_CONFIG,
        cb.MENU_INVITE,
        cb.MENU_STATUS,
        cb.MENU_HELP,
        cb.MENU_SETTINGS,
    ]


def test_back_keyboard() -> None:
    assert _callbacks(back_keyboard(Language.en)) == [cb.MENU_HOME]
