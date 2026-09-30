"""Check text against Telegram's HTML parse mode BEFORE it is sent.

Every bot message goes out with ``parse_mode=HTML`` (``DefaultBotProperties`` in the dispatcher and
the worker), and Telegram refuses the whole message when the markup does not parse. For a broadcast
that meant a lone ``<`` — "use the code <GOZAR>" — failed every single send, and the operator found
out only when the job finished: for the live install's audience, about 72 minutes later, with every
recipient counted as "failed". For a bot text it meant that screen stopped answering for everyone.

The rules mirror Telegram's own parser (``parse_html`` in tdlib), not a general HTML parser's:

* every ``<`` that is not escaped as ``&lt;`` must open a SUPPORTED tag — ``a < b`` and ``<3`` are
  errors, not text;
* an end tag must close the most recently opened one, and nothing may be left open;
* ``<span>`` must carry ``class="tg-spoiler"``.

``&`` is deliberately lenient: Telegram keeps an unknown entity as literal text rather than failing.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

#: https://core.telegram.org/bots/api#html-style
SUPPORTED_TAGS = frozenset(
    {
        "b",
        "strong",
        "i",
        "em",
        "u",
        "ins",
        "s",
        "strike",
        "del",
        "span",
        "tg-spoiler",
        "a",
        "tg-emoji",
        "code",
        "pre",
        "blockquote",
    }
)

# `<`, an optional `/`, a tag name, then anything up to the closing `>` that is not another `<`.
_TAG = re.compile(r"<(/?)([A-Za-z][A-Za-z0-9-]*)([^<>]*)>")
_CLASS = re.compile(r"""\bclass\s*=\s*(?:"([^"]*)"|'([^']*)'|([^\s"'>]+))""", re.IGNORECASE)


@dataclass(frozen=True, slots=True)
class HtmlProblem:
    """Why the text would not parse. ``kind`` is stable for the panel to phrase in its own words;
    ``tag`` names the offending tag (empty for a stray ``<``); ``offset`` is a character index."""

    kind: str  # "stray" | "unsupported" | "mismatch" | "unclosed" | "spoiler"
    tag: str
    offset: int

    def message(self) -> str:
        if self.kind == "stray":
            return f"a '<' at character {self.offset} is not a tag — write &lt; for a literal <"
        if self.kind == "unsupported":
            return f"<{self.tag}> is not a tag Telegram supports — write &lt; for a literal <"
        if self.kind == "mismatch":
            return f"</{self.tag}> at character {self.offset} closes a tag that is not open"
        if self.kind == "spoiler":
            return '<span> needs class="tg-spoiler" (or use <tg-spoiler>)'
        return f"<{self.tag}> is never closed"


def check(text: str) -> HtmlProblem | None:
    """The first problem Telegram would reject ``text`` for, or ``None`` when it parses."""
    stack: list[tuple[str, int]] = []
    i = 0
    while True:
        i = text.find("<", i)
        if i < 0:
            break
        match = _TAG.match(text, i)
        if match is None:
            return HtmlProblem("stray", "", i)
        closing, name, attrs = match.group(1), match.group(2).lower(), match.group(3)
        if name not in SUPPORTED_TAGS:
            return HtmlProblem("unsupported", name, i)
        if closing:
            if not stack or stack[-1][0] != name:
                return HtmlProblem("mismatch", name, i)
            stack.pop()
        else:
            if name == "span":
                found = _CLASS.search(attrs)
                value = next((g for g in found.groups() if g is not None), "") if found else ""
                if value != "tg-spoiler":
                    return HtmlProblem("spoiler", name, i)
            stack.append((name, i))
        i = match.end()
    if stack:
        name, at = stack[-1]
        return HtmlProblem("unclosed", name, at)
    return None
