"""Inline keyboard structure + namespaced callback data."""

from __future__ import annotations

from aiogram.types import InlineKeyboardMarkup

from gozar.bot import callbacks as cb
from gozar.bot.keyboards import (
    back_keyboard,
    config_delivered_keyboard,
    help_keyboard,
    landing_keyboard,
    language_keyboard,
    location_keyboard,
    main_menu_keyboard,
    settings_keyboard,
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


def test_help_keyboard_has_required_apps() -> None:
    # v1 attaches the required-apps button to the HELP screen (not the get-config picker).
    assert _callbacks(help_keyboard(Language.en)) == [cb.MENU_APPS, cb.MENU_HOME]


def test_settings_keyboard_language_and_reminder_toggle() -> None:
    # The reminder is a one-tap toggle right on the settings keyboard (same callback either way);
    # only its label differs by state, so the callbacks are identical for on/off.
    for enabled in (True, False):
        assert _callbacks(settings_keyboard(Language.en, reminder_enabled=enabled)) == [
            cb.SETTINGS_LANGUAGE,
            cb.SETTINGS_REMINDER_TOGGLE,
            cb.MENU_HOME,
        ]


def test_landing_keyboard_claimable() -> None:
    # The get-config landing for a claimable user: inner get-config + free-traffic + back.
    assert _callbacks(landing_keyboard(Language.en, active=False)) == [
        cb.CONFIG_CLAIM,
        cb.MENU_INVITE,
        cb.MENU_HOME,
    ]


def test_landing_keyboard_active() -> None:
    # Active user: change-location instead of get-config.
    assert _callbacks(landing_keyboard(Language.en, active=True)) == [
        cb.CONFIG_CHANGE,
        cb.MENU_INVITE,
        cb.MENU_HOME,
    ]


def test_config_delivered_keyboard_uses_new_message_home() -> None:
    assert _callbacks(config_delivered_keyboard(Language.en)) == [
        cb.CONFIG_CHANGE,
        cb.MENU_HOME_NEW,
    ]


def test_location_keyboard_short_locations_then_back_to_landing() -> None:
    kb = location_keyboard(["A", "B", "C"], cb.CONFIG_CLAIM_PREFIX, Language.en)
    assert _callbacks(kb) == [
        "config:claim:0",
        "config:claim:1",
        "config:claim:2",
        cb.MENU_CONFIG,  # 🏠 back to the landing (🔋 now lives on the landing)
    ]
    assert cb.MENU_INVITE not in _callbacks(kb)


def test_location_keyboard_paginates_by_global_index() -> None:
    remarks = [f"L{i}" for i in range(10)]  # 10 > _PAGE_SIZE (8) -> two pages

    page0 = _callbacks(location_keyboard(remarks, cb.CONFIG_CLAIM_PREFIX, Language.en, page=0))
    assert page0[:8] == [f"config:claim:{i}" for i in range(8)]
    assert cb.loc_page_cb("claim", 1) in page0  # Next only
    assert cb.loc_page_cb("claim", 0) not in page0
    assert page0[-1] == cb.MENU_CONFIG  # back to the landing
    assert cb.MENU_INVITE not in page0

    page1 = _callbacks(location_keyboard(remarks, cb.CONFIG_CLAIM_PREFIX, Language.en, page=1))
    assert page1[:2] == ["config:claim:8", "config:claim:9"]  # GLOBAL indices, not 0/1
    assert cb.loc_page_cb("claim", 0) in page1  # Prev only
    assert cb.loc_page_cb("claim", 1) not in page1


def test_location_keyboard_change_mode_uses_change_prefix_and_tag() -> None:
    remarks = [f"L{i}" for i in range(10)]
    page0 = _callbacks(location_keyboard(remarks, cb.CONFIG_CHANGE_PREFIX, Language.en, page=0))
    assert "config:change:0" in page0  # change delivery prefix
    assert cb.loc_page_cb("change", 1) in page0  # nav tag follows the change prefix


def test_location_keyboard_packs_two_per_row() -> None:
    kb = location_keyboard([f"L{i}" for i in range(5)], cb.CONFIG_CLAIM_PREFIX, Language.en)
    loc_rows = [
        row
        for row in kb.inline_keyboard
        if all((b.callback_data or "").startswith(cb.CONFIG_CLAIM_PREFIX) for b in row)
    ]
    assert [len(r) for r in loc_rows] == [2, 2, 1]  # 5 locations -> rows of 2, 2, 1


def test_location_keyboard_respects_page_size() -> None:
    remarks = [f"L{i}" for i in range(10)]
    page0 = _callbacks(
        location_keyboard(remarks, cb.CONFIG_CLAIM_PREFIX, Language.en, page=0, page_size=4)
    )
    locs = [c for c in page0 if c.startswith(cb.CONFIG_CLAIM_PREFIX)]
    assert locs == [f"config:claim:{i}" for i in range(4)]  # only 4 per page now
    assert cb.loc_page_cb("claim", 1) in page0  # smaller page size paginates sooner
