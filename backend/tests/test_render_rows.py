"""``render_rows`` — default layout is byte-identical to today; overrides apply correctly."""

from __future__ import annotations

from aiogram.types import InlineKeyboardMarkup

from gozar.db.models.enums import Language
from gozar.ui.buttons import ButtonOverrides, ButtonSpec, Override, render_rows

# Mirrors main_menu_keyboard's layout (.adjust(1, 2, 2)).
MAIN_MENU = [
    [ButtonSpec(key="menu_config", callback_data="menu:config")],
    [
        ButtonSpec(key="menu_invite", callback_data="menu:invite"),
        ButtonSpec(key="menu_status", callback_data="menu:status"),
    ],
    [
        ButtonSpec(key="menu_help", callback_data="menu:help"),
        ButtonSpec(key="menu_settings", callback_data="menu:settings"),
    ],
]


def _texts(m: InlineKeyboardMarkup) -> list[list[str]]:
    return [[b.text for b in row] for row in m.inline_keyboard]


def _callbacks(m: InlineKeyboardMarkup) -> list[list[str | None]]:
    return [[b.callback_data for b in row] for row in m.inline_keyboard]


def test_no_overrides_matches_default_layout() -> None:
    m = render_rows(Language.fa, MAIN_MENU)
    assert _texts(m) == [
        ["📥 دریافت کانفیگ امروز"],
        ["🗳 دعوت دوستان", "📊 وضعیت من"],
        ["📝 راهنما", "⚙️ تنظیمات"],
    ]
    assert _callbacks(m) == [
        ["menu:config"],
        ["menu:invite", "menu:status"],
        ["menu:help", "menu:settings"],
    ]


def test_label_override_per_language() -> None:
    ov = ButtonOverrides({"menu_config": Override(labels={"fa": "دریافت رایگان"})})
    assert _texts(render_rows(Language.fa, MAIN_MENU, ov))[0] == ["دریافت رایگان"]
    # No `en` override -> falls back to the default English label.
    assert _texts(render_rows(Language.en, MAIN_MENU, ov))[0] == ["📥 Get today's config"]


def test_hidden_non_critical_dropped_and_repacked() -> None:
    ov = ButtonOverrides({"menu_status": Override(is_visible=False)})
    assert _texts(render_rows(Language.fa, MAIN_MENU, ov)) == [
        ["📥 دریافت کانفیگ امروز"],
        ["🗳 دعوت دوستان"],  # invite now alone — row re-packed, no gap
        ["📝 راهنما", "⚙️ تنظیمات"],
    ]


def test_critical_button_never_hidden() -> None:
    structure = [
        [ButtonSpec(key="apps", callback_data="menu:apps")],
        [ButtonSpec(key="back", callback_data="menu:home")],  # critical
    ]
    ov = ButtonOverrides({"back": Override(is_visible=False)})  # ignored for criticals
    assert _texts(render_rows(Language.fa, structure, ov)) == [
        ["🔗 برنامه مورد نیاز"],
        ["🏠 بازگشت"],
    ]


def test_reorder_regroups_rows() -> None:
    ov = ButtonOverrides({"menu_help": Override(row=0, position=1)})
    m = render_rows(Language.fa, MAIN_MENU, ov)
    assert _texts(m)[0] == ["📥 دریافت کانفیگ امروز", "📝 راهنما"]
    assert _texts(m)[-1] == ["⚙️ تنظیمات"]  # help left row 2 -> settings alone


def test_raw_cell_bypasses_overrides() -> None:
    # Language-picker / location cells: explicit label, no key -> never overridden.
    structure = [[ButtonSpec(label="🇮🇷 فارسی", callback_data="lang:set:fa")]]
    assert _texts(render_rows(Language.en, structure)) == [["🇮🇷 فارسی"]]


def test_url_button_rendered() -> None:
    structure = [[ButtonSpec(key="invite_share", url="https://t.me/share")]]
    m = render_rows(Language.fa, structure)
    assert m.inline_keyboard[0][0].url == "https://t.me/share"
    assert m.inline_keyboard[0][0].text == "📤 اشتراک‌گذاری لینک"
