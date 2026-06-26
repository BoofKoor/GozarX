"""Inline keyboards. Button labels come from the in-code i18n map; callback data is namespaced."""

from __future__ import annotations

from aiogram.types import InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from gozar.bot import callbacks as cb
from gozar.bot.i18n import LANGUAGE_NAMES, t
from gozar.db.models.enums import Language


def language_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for lang in (Language.fa, Language.en, Language.ru):
        builder.button(text=LANGUAGE_NAMES[lang], callback_data=cb.lang_cb(lang.value))
    builder.adjust(1)
    return builder.as_markup()


def main_menu_keyboard(lang: Language) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text=t("menu_config", lang), callback_data=cb.MENU_CONFIG)
    builder.button(text=t("menu_invite", lang), callback_data=cb.MENU_INVITE)
    builder.button(text=t("menu_status", lang), callback_data=cb.MENU_STATUS)
    builder.button(text=t("menu_help", lang), callback_data=cb.MENU_HELP)
    builder.button(text=t("menu_settings", lang), callback_data=cb.MENU_SETTINGS)
    builder.adjust(1, 2, 2)  # config full-width, then invite/status and help/settings in pairs
    return builder.as_markup()


def back_keyboard(lang: Language) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text=t("back", lang), callback_data=cb.MENU_HOME)
    return builder.as_markup()
