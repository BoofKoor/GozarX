"""Inline keyboard structure + namespaced callback data."""

from __future__ import annotations

from aiogram.types import InlineKeyboardMarkup

from gozar.bot import callbacks as cb
from gozar.bot.keyboards import (
    back_keyboard,
    language_keyboard,
    location_keyboard,
    main_menu_keyboard,
)
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


def test_location_keyboard_short_has_actions_and_no_nav() -> None:
    kb = location_keyboard(["A", "B", "C"], cb.CONFIG_CLAIM_PREFIX, Language.en)
    assert _callbacks(kb) == [
        "config:claim:0",
        "config:claim:1",
        "config:claim:2",
        cb.MENU_INVITE,  # 🔋 free-traffic referral shortcut
        cb.MENU_APPS,  # 🔗 required apps
        cb.MENU_HOME,  # 🏠 back
    ]


def test_location_keyboard_paginates_by_global_index() -> None:
    remarks = [f"L{i}" for i in range(10)]  # 10 > _PAGE_SIZE (8) -> two pages

    page0 = _callbacks(location_keyboard(remarks, cb.CONFIG_CLAIM_PREFIX, Language.en, page=0))
    assert page0[:8] == [f"config:claim:{i}" for i in range(8)]
    assert cb.loc_page_cb("claim", 1) in page0  # Next only
    assert cb.loc_page_cb("claim", 0) not in page0
    assert page0[-3:] == [cb.MENU_INVITE, cb.MENU_APPS, cb.MENU_HOME]

    page1 = _callbacks(location_keyboard(remarks, cb.CONFIG_CLAIM_PREFIX, Language.en, page=1))
    assert page1[:2] == ["config:claim:8", "config:claim:9"]  # GLOBAL indices, not 0/1
    assert cb.loc_page_cb("claim", 0) in page1  # Prev only
    assert cb.loc_page_cb("claim", 1) not in page1


def test_location_keyboard_change_mode_keeps_loc_tag() -> None:
    remarks = [f"L{i}" for i in range(10)]
    page0 = _callbacks(location_keyboard(remarks, cb.CONFIG_LOC_PREFIX, Language.en, page=0))
    assert "config:loc:0" in page0
    assert cb.loc_page_cb("loc", 1) in page0  # nav tag follows the LOC (change) prefix
