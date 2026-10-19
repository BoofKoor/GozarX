"""Premium emoji: which emoji become custom emoji (and where they must not), button icons, the
location flags of the users' picker, and the look snapshot that switches all of it off."""

from __future__ import annotations

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from gozar.ui import icons
from gozar.ui.flags import (
    country_code,
    flag_emoji,
    flag_keyboard,
    location_button,
    location_html,
    split_flag,
    with_flag,
)
from gozar.ui.look import PLAIN, Look
from gozar.ui.theme import NOOP, button_icon, strip_icons, theme_html, theme_markup
from gozar.ui.validate import check_classic, check_keyboard

ON = Look()
DE = icons.FLAGS["DE"]


def test_known_emoji_in_text_become_custom_emoji_with_the_emoji_as_alternative() -> None:
    html, n = theme_html("🏠 menu • 🇩🇪 DE", ON.text_icon)
    assert n == 2
    assert f'<tg-emoji emoji-id="{icons.TEXT["🏠"]}">🏠</tg-emoji>' in html
    assert f'<tg-emoji emoji-id="{DE}">🇩🇪</tg-emoji>' in html
    assert check_classic(html) == []


def test_code_links_and_times_keep_their_emoji_literal() -> None:
    src = '<code>🏠</code> <a href="https://x.y">🏠</a> <tg-time unix="1" format="t">🏠</tg-time>'
    html, n = theme_html(src, ON.text_icon)
    assert n == 0 and html == src


def test_an_emoji_inside_a_bigger_one_is_left_whole() -> None:
    # 💻 ends 🧑‍💻 (a ZWJ sequence); 👆 with a skin tone is another emoji — neither may be split.
    for src in ("🧑‍💻 dev", "👆🏽 up"):
        html, n = theme_html(src, ON.text_icon)
        assert n == 0 and html == src


def test_a_button_label_gives_its_leading_emoji_to_the_icon() -> None:
    assert button_icon("🗑 حذف", ON.button_icon) == ("حذف", icons.COLOR["🗑"])
    # on a coloured button the adaptive (MONO/SF) icon, never the coloured Twemoji
    assert button_icon("🔄 again", ON.button_icon, coloured_button=True) == (
        "again",
        icons.MONO["🔄"],
    )
    assert button_icon("no emoji", ON.button_icon) == ("no emoji", None)
    assert button_icon("🗑", ON.button_icon) == ("🗑", None)  # nothing would be left


def test_theme_markup_icons_and_disabled_info_cells() -> None:
    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🗑 Delete", callback_data="x:del", style="danger")],
            [InlineKeyboardButton(text="page 2/5", callback_data=NOOP)],
        ]
    )
    themed = theme_markup(kb, ON.button_icon)
    delete, page = themed.inline_keyboard[0][0], themed.inline_keyboard[1][0]
    assert delete.text == "Delete" and delete.icon_custom_emoji_id
    assert page.disabled is not None and page.callback_data is None
    assert check_keyboard(themed) == []
    # without icons the label is untouched, but the info cell is still disabled
    plain = theme_markup(kb, None)
    assert plain.inline_keyboard[0][0].text == "🗑 Delete"
    assert plain.inline_keyboard[1][0].disabled is not None
    assert strip_icons(themed).inline_keyboard[0][0].icon_custom_emoji_id is None


def test_the_snapshot_switches_icons_off() -> None:
    assert ON.icons_on and not PLAIN.icons_on
    assert not Look(blocked=True).icons_on  # Telegram refused them: plain until the block ends
    assert Look(missing=frozenset({DE})).flag_id("DE") is None  # an id Telegram doesn't know
    assert PLAIN.flag_id("DE") is None
    assert ON.flag_id("de") == DE


def test_a_remark_names_its_country_the_way_the_site_reads_it() -> None:
    cases = {
        "🇩🇪 آلمان": "DE",
        "آلمان ۲": "DE",
        "آلمان۲": "DE",
        "Germany-2": "DE",
        "سرور هلند": "NL",
        "UK 2": "GB",
        "Ukraine": "UA",  # not "uk"
        "هنگ‌کنگ": "HK",
        "DE": "DE",
        "🇸🇾 Syria": "SY",  # a flag names its country even without a premium flag for it
    }
    for remark, code in cases.items():
        assert country_code(remark) == code, remark
    for remark in ("WARP", "کوچک", "duke", "ok"):  # «چک» / "uk" only as a whole word
        assert country_code(remark) is None, remark


def test_the_picker_button_trades_its_flag_for_the_premium_icon() -> None:
    assert split_flag("🇩🇪 آلمان ۲") == ("DE", "آلمان ۲")
    assert split_flag("Finland 🇫🇮") == ("FI", "Finland")
    assert split_flag("🇩🇪") == (None, "🇩🇪")  # nothing would be left
    assert location_button("🇩🇪 آلمان", ON) == ("آلمان", DE)
    assert location_button("آلمان", ON) == ("آلمان", DE)  # named only: the icon is added
    assert location_button("🇩🇪 آلمان", PLAIN) == ("🇩🇪 آلمان", None)  # off: exactly the remark
    assert location_button("WARP", ON) == ("WARP", None)


def test_the_delivered_text_draws_the_flag_as_a_premium_emoji() -> None:
    assert location_html("🇩🇪 آلمان", ON) == f'<tg-emoji emoji-id="{DE}">🇩🇪</tg-emoji> آلمان'
    assert location_html("آلمان", ON) == f'<tg-emoji emoji-id="{DE}">🇩🇪</tg-emoji> آلمان'
    assert location_html("<b>DE</b>", PLAIN) == "&lt;b&gt;DE&lt;/b&gt;"
    assert location_html("WARP & co", ON) == "WARP &amp; co"
    assert check_classic(location_html("🇩🇪 آلمان & co", ON)) == []
    assert with_flag("آلمان") == f"{flag_emoji('DE')} آلمان"
    assert with_flag("🇳🇱 هلند") == "🇳🇱 هلند"


def test_flag_keyboard_touches_only_the_location_cells() -> None:
    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="🇩🇪 آلمان", callback_data="config:claim:0"),
                InlineKeyboardButton(text="هلند", callback_data="config:claim:1"),
            ],
            [InlineKeyboardButton(text="Next ➡️", callback_data="loc:page:claim:1")],
        ]
    )
    remarks = {"config:claim:0": "🇩🇪 آلمان", "config:claim:1": "هلند"}
    themed = flag_keyboard(kb, remarks, ON)
    first, second = themed.inline_keyboard[0]
    assert (first.text, first.icon_custom_emoji_id) == ("آلمان", DE)
    assert (second.text, second.icon_custom_emoji_id) == ("هلند", icons.FLAGS["NL"])
    assert themed.inline_keyboard[1][0].icon_custom_emoji_id is None  # chrome is left alone
    assert flag_keyboard(kb, remarks, PLAIN) is kb  # same object: nothing to fall back from


def test_every_icon_id_is_a_custom_emoji_id() -> None:
    ids = icons.all_ids()
    assert len(ids) == 403
    assert all(i.isdigit() and len(i) >= 18 for i in ids)
    assert len(icons.FLAGS) == 256 and "SY" not in icons.FLAGS
    assert len(set(icons.FLAGS.values())) == 256  # no two countries share a flag
