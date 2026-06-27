"""Inline keyboards. Button labels come from the in-code i18n map; callback data is namespaced."""

from __future__ import annotations

from urllib.parse import quote

from aiogram.types import InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from gozar.bot import callbacks as cb
from gozar.bot.i18n import LANGUAGE_NAMES, t
from gozar.db.models.enums import Language

# Locations per picker page; longer squads paginate with Next/Prev (v1's after_before_keyboard).
_PAGE_SIZE = 8


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


def help_keyboard(lang: Language) -> InlineKeyboardMarkup:
    """Help screen — carries the required-apps shortcut (v1 attaches it here, not to the picker)."""
    builder = InlineKeyboardBuilder()
    builder.button(text=t("apps", lang), callback_data=cb.MENU_APPS)
    builder.button(text=t("back", lang), callback_data=cb.MENU_HOME)
    builder.adjust(1)
    return builder.as_markup()


def landing_keyboard(lang: Language, *, active: bool) -> InlineKeyboardMarkup:
    """Get-config landing (v1). Claimable -> a get-config button that provisions on tap; active ->
    a change-location button. Both carry the 🔋 free-traffic referral shortcut + back."""
    builder = InlineKeyboardBuilder()
    if active:
        builder.button(text=t("change_location", lang), callback_data=cb.CONFIG_CHANGE)
    else:
        builder.button(text=t("get_config", lang), callback_data=cb.CONFIG_CLAIM)
    builder.button(text=t("increase_traffic", lang), callback_data=cb.MENU_INVITE)
    builder.button(text=t("back", lang), callback_data=cb.MENU_HOME)
    builder.adjust(1)
    return builder.as_markup()


def location_keyboard(
    remarks: list[str], prefix: str, lang: Language, *, page: int = 0
) -> InlineKeyboardMarkup:
    """Paginated picker over location remark NAMES.

    Each button is keyed by its **global** index, and the chosen name resolves to its link by NAME
    (never a cross-index between two lists). ``page`` is a pure view offset into the same cached
    remarks. Below the locations: a Prev/Next nav row (only when there's more than one page), then
    back to the landing (the 🔋 free-traffic shortcut lives on the landing, not here).
    """
    builder = InlineKeyboardBuilder()
    page_count = max(1, (len(remarks) + _PAGE_SIZE - 1) // _PAGE_SIZE)
    page = min(max(page, 0), page_count - 1)
    window = range(page * _PAGE_SIZE, min((page + 1) * _PAGE_SIZE, len(remarks)))
    for index in window:
        builder.button(text=remarks[index], callback_data=f"{prefix}{index}")
    sizes = [1] * len(window)

    tag = "claim" if prefix == cb.CONFIG_CLAIM_PREFIX else "change"
    nav = 0
    if page > 0:
        builder.button(text=t("nav_prev", lang), callback_data=cb.loc_page_cb(tag, page - 1))
        nav += 1
    if page < page_count - 1:
        builder.button(text=t("nav_next", lang), callback_data=cb.loc_page_cb(tag, page + 1))
        nav += 1
    if nav:
        sizes.append(nav)  # Prev/Next share one row

    builder.button(text=t("back", lang), callback_data=cb.MENU_CONFIG)  # back to the landing
    sizes.append(1)
    builder.adjust(*sizes)
    return builder.as_markup()


def config_delivered_keyboard(lang: Language) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text=t("change_location", lang), callback_data=cb.CONFIG_CHANGE)
    # "show main menu" sends a NEW message (MENU_HOME_NEW) so the delivered config stays in chat.
    builder.button(text=t("show_menu", lang), callback_data=cb.MENU_HOME_NEW)
    builder.adjust(1)
    return builder.as_markup()


def status_keyboard(lang: Language, *, active: bool) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    if active:
        builder.button(text=t("change_location", lang), callback_data=cb.CONFIG_CHANGE)
    builder.button(text=t("back", lang), callback_data=cb.MENU_HOME)
    builder.adjust(1)
    return builder.as_markup()


def settings_keyboard(lang: Language) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text=t("settings_language", lang), callback_data=cb.SETTINGS_LANGUAGE)
    builder.button(text=t("settings_reminder", lang), callback_data=cb.SETTINGS_REMINDER)
    builder.button(text=t("back", lang), callback_data=cb.MENU_HOME)
    builder.adjust(2, 1)  # language | reminder on one row, back below
    return builder.as_markup()


def reminder_keyboard(lang: Language, *, reminder_enabled: bool) -> InlineKeyboardMarkup:
    """Reminder sub-screen: one state toggle (enable when off / disable when on) + back."""
    builder = InlineKeyboardBuilder()
    if reminder_enabled:
        builder.button(text=t("reminder_disable", lang), callback_data=cb.SETTINGS_REMINDER_OFF)
    else:
        builder.button(text=t("reminder_enable", lang), callback_data=cb.SETTINGS_REMINDER_ON)
    builder.button(text=t("back", lang), callback_data=cb.MENU_SETTINGS)
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
