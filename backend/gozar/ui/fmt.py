"""Small formatters for console screens: numbers in the reader's digits, and instants as
``<tg-time>`` (Bot API 9.5) so Telegram prints them in the reader's own clock and format.

Every value comes back as HTML-safe text, ready for a ``Doc`` cell.
"""

from __future__ import annotations

import html
from datetime import UTC, datetime

from gozar.config.reporting import DISPLAY_TZ
from gozar.db.models.enums import Language

esc = html.escape

_FA_DIGITS = str.maketrans("0123456789", "۰۱۲۳۴۵۶۷۸۹")


def digits(text: str, lang: Language) -> str:
    """Latin digits → Persian ones for a Persian reader, with «٬» between thousands and «٫» for a
    decimal point between two digits (what ``Intl`` prints, so a console figure reads like the
    web panel's)."""
    if lang is not Language.fa:
        return text
    out = []
    for i, ch in enumerate(text):
        between = 0 < i < len(text) - 1 and text[i - 1].isdigit() and text[i + 1].isdigit()
        if ch == "," and between:
            out.append("٬")
        elif ch == "." and between:
            out.append("٫")
        else:
            out.append(ch)
    return "".join(out).translate(_FA_DIGITS)


def num(value: int | float | None, lang: Language) -> str:
    """A count with thousands separators, in the reader's digits; «—» for an unknown figure."""
    if value is None:
        return "—"
    text = f"{value:,}" if isinstance(value, int) else f"{value:,.1f}"
    return digits(text, lang)


def pct(part: int, whole: int, lang: Language) -> str:
    """``part`` of ``whole`` as a percentage; «—» when there is no whole to be a share of."""
    if whole <= 0:
        return "—"
    return digits(f"{round(100 * part / whole)}%", lang)


def _aware(instant: datetime) -> datetime:
    return instant if instant.tzinfo else instant.replace(tzinfo=UTC)


def when(instant: datetime | None, lang: Language, fmt: str = "dt") -> str:
    """An instant Telegram prints in the reader's own time zone and format (``fmt``: w = weekday,
    d/D = short/long date, t/T = short/long time). The text inside is the fallback for an app that
    can't: the Tehran clock, in the reader's digits."""
    if instant is None:
        return "—"
    moment = _aware(instant)
    fallback = digits(moment.astimezone(DISPLAY_TZ).strftime("%Y-%m-%d %H:%M"), lang)
    return f'<tg-time unix="{int(moment.timestamp())}" format="{fmt}">{fallback}</tg-time>'


def ago(instant: datetime | None, lang: Language) -> str:
    """An instant as relative time ("5 minutes ago"), kept current by the app itself."""
    if instant is None:
        return "—"
    moment = _aware(instant)
    fallback = digits(moment.astimezone(DISPLAY_TZ).strftime("%Y-%m-%d %H:%M"), lang)
    return f'<tg-time unix="{int(moment.timestamp())}" format="r">{fallback}</tg-time>'
