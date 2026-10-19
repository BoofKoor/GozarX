"""Plain emoji → Telegram custom emoji, in an HTML text and on a keyboard. Pure functions.

A screen keeps writing ordinary emoji; the sender (``bot/screens``) runs these over what it sends
when the snapshot's icons are on, so a non-premium bot is byte-for-byte what the screen wrote.

- ``theme_html``: every known emoji in the TEXT parts of an HTML string becomes
  ``<tg-emoji emoji-id="…">emoji</tg-emoji>`` (the Unicode emoji stays as the alternative text).
  Tags, their attributes, and the text inside code/pre/links/tg-time are copied unchanged.
- ``button_icon``: a label that starts with a known emoji ("🗑 حذف") gives the emoji to the button's
  ``icon_custom_emoji_id`` and keeps the words ("حذف"). A plain button gets the coloured icon, a
  green / red / blue one the adaptive one (white on the colour).
- ``theme_markup``: both of the above over an inline keyboard, plus the information-only button:
  callback data ``NOOP`` becomes a disabled button (Bot API 10.3).
"""

from __future__ import annotations

import re
from collections.abc import Callable

from aiogram.types import DisabledButton, InlineKeyboardButton, InlineKeyboardMarkup

from gozar.ui.icons import BUTTON, COLOR, NAMED, TEXT, VS16, norm

#: Callback data of a button that only shows something (a page number, a table cell's value).
NOOP = "ui:noop"

# a tag: <name ...>, </name> or <name .../>; our HTML escapes every < and > that isn't markup
TAG_RX = re.compile(r"<(/?)([A-Za-z][\w-]*)[^>]*?(/?)>")
# text inside these is left alone: code must stay literal, a tg-emoji already is one, tg-time's text
# is a fallback, a link's text may not take custom emoji
SKIP = {"code", "pre", "tg-emoji", "tg-time", "tg-math", "tg-math-block", "a", "img"}
VOID = {"br", "hr", "img", "input"}

_KEYS = sorted(set(TEXT) | set(NAMED), key=len, reverse=True)
# one emoji we know (optionally with VS16) that is a WHOLE emoji — not inside a ZWJ sequence
# (🧑‍💻, 🚶‍➡️, 👁️‍🗨️) and not with a skin tone (👆🏽): names typed by an operator may have those —
# or a flag (two regional indicators)
EMOJI_RX = re.compile(
    "(?<!‍)(?:"
    + "|".join(map(re.escape, _KEYS))
    + ")(?![\U0001f3fb-\U0001f3ff])(?!"
    + VS16
    + "?‍)"
    + VS16
    + "?|[\U0001f1e6-\U0001f1ff]{2}"
)

#: text: (emoji, the text right after it) -> id; buttons: (emoji, coloured_button) -> id
IconFor = Callable[..., "str | None"]
AFTER = 24  # how much of the text after a mark is read for its name (icons.NAMED)


def _sub(text: str, icon_for: IconFor) -> tuple[str, int]:
    count = 0

    def one(m: re.Match[str]) -> str:
        nonlocal count
        eid = icon_for(m.group(0), m.string[m.end() : m.end() + AFTER])
        if not eid:
            return m.group(0)
        count += 1
        return f'<tg-emoji emoji-id="{eid}">{m.group(0)}</tg-emoji>'

    return EMOJI_RX.sub(one, text), count


def theme_html(markup: str, icon_for: IconFor) -> tuple[str, int]:
    """Wrap every known emoji of the text parts of ``markup`` in ``<tg-emoji>``.

    Returns ``(html, how many)``. Tags and their attributes, and the text inside SKIP tags, are
    copied unchanged."""
    out: list[str] = []
    skip: list[str] = []
    pos = count = 0
    for m in TAG_RX.finditer(markup):
        text = markup[pos : m.start()]
        if skip:
            out.append(text)
        else:
            themed, k = _sub(text, icon_for)
            out.append(themed)
            count += k
        closing, name, selfclosing = m.group(1) == "/", m.group(2).lower(), m.group(3) == "/"
        if name in SKIP and name not in VOID and not selfclosing:
            if closing:
                if name in skip:  # close the innermost one of that name
                    del skip[len(skip) - 1 - skip[::-1].index(name)]
            else:
                skip.append(name)
        out.append(m.group(0))
        pos = m.end()
    tail = markup[pos:]
    if skip:
        out.append(tail)
    else:
        themed, k = _sub(tail, icon_for)
        out.append(themed)
        count += k
    return "".join(out), count


_LEAD_KEYS = sorted(set(TEXT) | set(BUTTON) | set(COLOR), key=len, reverse=True)
LEAD_RX = re.compile(
    "^(" + "|".join(map(re.escape, _LEAD_KEYS)) + "|[\U0001f1e6-\U0001f1ff]{2})" + VS16 + r"?\s+"
)


def button_icon(
    text: str, icon_for: IconFor, coloured_button: bool = False
) -> tuple[str, str | None]:
    """'🗑 حذف' -> ('حذف', id of 🗑); '🇩🇪 DE-1' -> ('DE-1', the German flag).

    A label that doesn't start with a known emoji — or that would be empty without it — comes back
    unchanged with None."""
    m = LEAD_RX.match(text)
    if not m:
        return text, None
    rest = text[m.end() :]
    if not rest.strip():
        return text, None
    eid = icon_for(norm(m.group(1)), coloured_button)
    if not eid:
        return text, None
    return rest, eid


def theme_button(button: InlineKeyboardButton, icon_for: IconFor | None) -> InlineKeyboardButton:
    """An information-only ``NOOP`` button becomes a disabled one; with icons on, the label's
    leading emoji becomes the button's icon (coloured on a plain button, adaptive on a coloured
    one). A button that already carries an icon keeps it."""
    upd: dict[str, object] = {}
    if button.callback_data == NOOP:
        upd.update(callback_data=None, disabled=DisabledButton())
    if icon_for is not None and button.icon_custom_emoji_id is None:
        text, eid = button_icon(button.text, icon_for, coloured_button=button.style is not None)
        if eid:
            upd.update(text=text, icon_custom_emoji_id=eid)
    return button.model_copy(update=upd) if upd else button


def theme_markup(markup: object, icon_for: IconFor | None) -> object:
    """A copy of an inline keyboard with its icons (and disabled info buttons); anything else — a
    reply keyboard, ``None`` — comes back as it is."""
    if not isinstance(markup, InlineKeyboardMarkup):
        return markup
    rows = [[theme_button(b, icon_for) for b in row] for row in markup.inline_keyboard]
    unchanged = all(
        nb is ob
        for new_row, old_row in zip(rows, markup.inline_keyboard, strict=True)
        for nb, ob in zip(new_row, old_row, strict=True)
    )
    return markup if unchanged else markup.model_copy(update={"inline_keyboard": rows})


def strip_icons(markup: object) -> object:
    """The same keyboard with every custom-emoji icon removed — the fallback when Telegram refuses
    a keyboard because of one (a stale id, or an owner without Premium)."""
    if not isinstance(markup, InlineKeyboardMarkup):
        return markup
    if not any(b.icon_custom_emoji_id for row in markup.inline_keyboard for b in row):
        return markup
    rows = [
        [b.model_copy(update={"icon_custom_emoji_id": None}) for b in row]
        for row in markup.inline_keyboard
    ]
    return markup.model_copy(update={"inline_keyboard": rows})
