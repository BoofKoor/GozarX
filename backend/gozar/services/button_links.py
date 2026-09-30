"""What Telegram accepts on an inline URL button — one rule for the bot and the panel.

The bot checked it only when RENDERING the promo button: a link typed as ``t.me/x`` saved without a
word from the panel, and the bot then silently left the button out of every delivered config. The
panel's settings PUT now refuses what the bot would drop, using this same function.
"""

from __future__ import annotations

_SCHEMES = ("http://", "https://", "tg://")

#: Persian and Arabic-Indic digits → ASCII. A custom-emoji id is a number, and the only keyboard an
#: operator has may type «۵۳۶۸…».
_DIGITS = str.maketrans("۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩", "01234567890123456789")


def is_button_url(url: str) -> bool:
    """Whether Telegram will take ``url`` on a URL button (http(s) and ``tg://`` links)."""
    return url.startswith(_SCHEMES)


def normalize_emoji_id(raw: str) -> str | None:
    """A custom-emoji id as ASCII digits; ``""`` for blank; ``None`` when it is not a number."""
    value = raw.strip().translate(_DIGITS)
    if not value:
        return ""
    return value if value.isascii() and value.isdigit() else None
