"""Inline keyboards. Button labels come from the in-code i18n map; callback data is namespaced."""

from __future__ import annotations

from urllib.parse import quote

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


def location_keyboard(remarks: list[str], prefix: str, lang: Language) -> InlineKeyboardMarkup:
    """Picker over location remark NAMES. The button index addresses the cached picker, and the
    chosen name is resolved to its link by name — never a cross-index between two lists.
    """
    builder = InlineKeyboardBuilder()
    for index, remark in enumerate(remarks):
        builder.button(text=remark, callback_data=f"{prefix}{index}")
    builder.button(text=t("back", lang), callback_data=cb.MENU_HOME)
    builder.adjust(1)
    return builder.as_markup()


def config_delivered_keyboard(lang: Language) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text=t("change_location", lang), callback_data=cb.CONFIG_CHANGE)
    builder.button(text=t("back", lang), callback_data=cb.MENU_HOME)
    builder.adjust(1)
    return builder.as_markup()


def status_keyboard(lang: Language, *, active: bool) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    if active:
        builder.button(text=t("change_location", lang), callback_data=cb.CONFIG_CHANGE)
    builder.button(text=t("back", lang), callback_data=cb.MENU_HOME)
    builder.adjust(1)
    return builder.as_markup()


def settings_keyboard(lang: Language, *, reminder_enabled: bool) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text=t("settings_language", lang), callback_data=cb.SETTINGS_LANG)
    toggle = t("reminder_on", lang) if reminder_enabled else t("reminder_off", lang)
    builder.button(text=toggle, callback_data=cb.SETTINGS_REMINDER_TOGGLE)
    builder.button(text=t("back", lang), callback_data=cb.MENU_HOME)
    builder.adjust(1)
    return builder.as_markup()


def invite_keyboard(lang: Language, link: str) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    if link.startswith("http"):  # a real deep link (bot_username configured) — offer one-tap share
        builder.button(
            text=t("invite_share", lang), url=f"https://t.me/share/url?url={quote(link)}"
        )
    builder.button(text=t("back", lang), callback_data=cb.MENU_HOME)
    builder.adjust(1)
    return builder.as_markup()
