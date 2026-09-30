"""``telegram_html.check`` refuses what Telegram's HTML parse mode would refuse — no more, no less.

Every bot message is sent as HTML, so a stray ``<`` in a broadcast failed every send (and was found
out only when the job ended), and in a bot text it silenced that screen.
"""

from __future__ import annotations

import pytest

from gozar.seed import DEFAULT_CONTENT
from gozar.services.telegram_html import check


@pytest.mark.parametrize(
    "text",
    [
        "plain text, no markup",
        "<b>bold</b> <i>it</i> <u>u</u> <s>s</s> <code>x</code> <pre>y</pre>",
        '<a href="https://t.me/x">link</a> and <tg-spoiler>secret</tg-spoiler>',
        '<span class="tg-spoiler">hidden</span>',
        "<blockquote expandable>quote</blockquote>",
        "&lt;GOZAR&gt; is escaped, and Tom & Jerry keeps a bare ampersand",
        "<B>case</B> does not matter",
        "5 > 3 is fine: only the opening bracket has to be escaped",
        "<b><i>nested</i></b>",
    ],
)
def test_what_telegram_accepts_passes(text: str) -> None:
    assert check(text) is None


@pytest.mark.parametrize(
    ("text", "kind"),
    [
        ("use the code <GOZAR> to join", "unsupported"),
        ("a < b", "stray"),
        ("I <3 this", "stray"),
        ("<b>never closed", "unclosed"),
        ("<b><i>crossed</b></i>", "mismatch"),
        ("stray close</b>", "mismatch"),
        ("<span>no class</span>", "spoiler"),
        ("line<br>break", "unsupported"),
    ],
)
def test_what_telegram_rejects_is_named(text: str, kind: str) -> None:
    problem = check(text)
    assert problem is not None and problem.kind == kind


def test_every_seeded_bot_text_parses() -> None:
    # The gate must not refuse the copy the bot ships with.
    for key, bodies in DEFAULT_CONTENT.items():
        for lang, body in bodies.items():
            assert check(body) is None, (key, lang, check(body))
