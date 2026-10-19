"""Checks a console screen against Telegram's documented markup rules (Bot API 10.3) — what the
tests run over every screen the console renders, so a tag Telegram would refuse fails a test
instead of a live screen.

Covers the tags of "Rich HTML style" and "HTML style", the named entities each one accepts, proper
nesting, ``<tg-emoji>`` / ``<tg-time>`` / ``<tg-button>`` attributes, the rich message limits
(32768 characters, 500 blocks, 16 levels, 20 table columns), and keyboard buttons.
"""

from __future__ import annotations

import html
import re
from html.parser import HTMLParser

from aiogram.types import InlineKeyboardMarkup

RICH_TAGS = {
    "b", "strong", "i", "em", "u", "ins", "s", "strike", "del", "code", "mark", "sub", "sup",
    "tg-spoiler", "a", "tg-reference", "tg-emoji", "img", "tg-time", "tg-math", "h1", "h2", "h3",
    "h4", "h5", "h6", "p", "pre", "footer", "hr", "ul", "ol", "li", "input", "blockquote", "cite",
    "aside", "video", "audio", "tg-document", "figure", "figcaption", "tg-map", "tg-collage",
    "tg-slideshow", "table", "caption", "tr", "th", "td", "details", "summary", "tg-math-block",
    "tg-button", "tg-button-row", "br",
}  # fmt: skip
CLASSIC_TAGS = {
    "b", "strong", "i", "em", "u", "ins", "s", "strike", "del", "span", "tg-spoiler", "a",
    "tg-emoji", "tg-time", "code", "pre", "blockquote",
}  # fmt: skip
VOID = {"br", "hr", "img", "input", "tg-map"}
RICH_ENTITIES = {
    "lt", "gt", "amp", "quot", "apos", "nbsp", "hellip", "mdash", "ndash", "lsquo", "rsquo",
    "ldquo", "rdquo",
}  # fmt: skip
CLASSIC_ENTITIES = {"lt", "gt", "amp", "quot"}
# what counts towards the 500 blocks: "nested blocks, list items, table rows, quotation blocks,
# details blocks"
BLOCKS = {
    "h1", "h2", "h3", "h4", "h5", "h6", "p", "pre", "footer", "hr", "ul", "ol", "li", "blockquote",
    "aside", "table", "tr", "details", "tg-button-row", "tg-math-block", "figure", "tg-map",
    "tg-collage", "tg-slideshow",
}  # fmt: skip
BUTTON_TYPES = {
    "url", "callback_data", "web_app", "login_url", "switch_inline_query",
    "switch_inline_query_current_chat", "switch_inline_query_chosen_chat", "copy_text", "disabled",
}  # fmt: skip


# Telegram's nesting rules for a REGULAR message ("Formatting options"): bold, italic, underline,
# strikethrough and spoiler can contain and be part of anything except pre and code; blockquotes
# can't be nested; all other entities (code, pre, links, custom emoji, times) can't contain each
# other. A rich message has its own structure and none of these limits.
_STYLE = {"b", "strong", "i", "em", "u", "ins", "s", "strike", "del", "tg-spoiler", "span"}
_SOLID = {"code", "pre", "a", "tg-emoji", "tg-time"}


def _nesting(tag: str, stack: list[str]) -> str | None:
    if tag in ("code", "pre") and any(t in _STYLE for t in stack):
        return f"<{tag}> inside a style tag ({'/'.join(stack)})"
    if tag in _STYLE and any(t in ("code", "pre") for t in stack):
        return f"<{tag}> inside code"
    if tag in _SOLID and any(t in _SOLID for t in stack):
        if not (tag == "code" and stack[-1:] == ["pre"]):  # <pre><code class=…> is the one pair
            return f"<{tag}> inside <{next(t for t in stack if t in _SOLID)}>"
    if tag == "blockquote" and "blockquote" in stack:
        return "a blockquote inside a blockquote"
    return None


class _Checker(HTMLParser):
    def __init__(self, allowed: set[str], entities: set[str], nesting: bool = False) -> None:
        super().__init__(convert_charrefs=False)
        self.allowed, self.entities, self.nesting = allowed, entities, nesting
        self.problems: list[str] = []
        self.stack: list[str] = []
        self.depth = self.blocks = 0
        self.text: list[str] = []
        self.cols: list[int] = []
        self.emoji_open: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        a = dict(attrs)
        if tag not in self.allowed:
            self.problems.append(f"tag <{tag}> isn't supported")
        if tag == "span" and a.get("class") != "tg-spoiler":
            self.problems.append("<span> must be class=tg-spoiler")
        if tag == "tg-emoji":
            if not re.fullmatch(r"\d+", a.get("emoji-id") or ""):
                self.problems.append("<tg-emoji> needs a numeric emoji-id")
            self.emoji_open.append("")
        if tag == "tg-time":
            if not re.fullmatch(r"\d+", a.get("unix") or ""):
                self.problems.append("<tg-time> needs unix")
            if not re.fullmatch(r"r|w?[dD]?[tT]?", a.get("format") or ""):
                self.problems.append(f"<tg-time> format {a.get('format')!r}")
        if tag == "tg-button":
            kind = a.get("type")
            if kind not in BUTTON_TYPES:
                self.problems.append(f"<tg-button> type {kind!r}")
            if kind == "copy_text" and not a.get("text"):
                self.problems.append("copy_text button without text")
            if kind == "callback_data" and not 1 <= len((a.get("data") or "").encode()) <= 64:
                self.problems.append("callback data must be 1-64 bytes")
            if a.get("style") not in (None, "danger", "success", "primary", "link"):
                self.problems.append(f"button style {a.get('style')!r}")
            if a.get("style") == "link" and kind != "callback_data":
                self.problems.append("style link is for callback buttons only")
        if tag == "tr":
            self.cols.append(0)
        if tag in ("td", "th") and self.cols:
            self.cols[-1] += int(a.get("colspan") or 1)
            if self.cols[-1] > 20:
                self.problems.append("more than 20 columns in a table")
        if tag in BLOCKS:
            self.blocks += 1
        if self.nesting:
            problem = _nesting(tag, self.stack)
            if problem:
                self.problems.append(problem)
        if tag in VOID:
            return
        self.stack.append(tag)
        self.depth = max(self.depth, len(self.stack))

    def handle_startendtag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self.handle_starttag(tag, attrs)
        if tag not in VOID and self.stack and self.stack[-1] == tag:
            self.stack.pop()

    def handle_endtag(self, tag: str) -> None:
        if tag in VOID:
            return
        if not self.stack or self.stack[-1] != tag:
            innermost = self.stack[-1:] or "none"
            self.problems.append(f"</{tag}> doesn't close the innermost open tag ({innermost})")
            if tag in self.stack:
                while self.stack and self.stack.pop() != tag:
                    pass
            return
        self.stack.pop()
        if tag == "tg-emoji":
            alt = self.emoji_open.pop() if self.emoji_open else ""
            if not alt.strip():
                self.problems.append("<tg-emoji> without its alternative emoji")

    def handle_data(self, data: str) -> None:
        self.text.append(data)
        if self.emoji_open:
            self.emoji_open[-1] += data

    def handle_entityref(self, name: str) -> None:
        if name not in self.entities:
            self.problems.append(f"entity &{name}; isn't supported")
        self.text.append(html.unescape(f"&{name};"))

    def handle_charref(self, name: str) -> None:
        self.text.append(html.unescape(f"&#{name};"))


def _check(markup: str, allowed: set[str], entities: set[str], nesting: bool = False) -> _Checker:
    c = _Checker(allowed, entities, nesting)
    c.feed(markup)
    c.close()
    if c.stack:
        c.problems.append(f"not closed: {c.stack}")
    # a bare & that isn't an entity would break Telegram's parser
    for m in re.finditer(r"&(?!(#\d+|#x[0-9a-fA-F]+|[A-Za-z]+);)", markup):
        c.problems.append(f"bare & at {m.start()}")
    return c


def check_rich(markup: str) -> list[str]:
    c = _check(markup, RICH_TAGS, RICH_ENTITIES)
    text = "".join(c.text)
    if len(text) > 32768:
        c.problems.append(f"{len(text)} characters (max 32768)")
    if c.blocks > 500:
        c.problems.append(f"{c.blocks} blocks (max 500)")
    if c.depth > 16:
        c.problems.append(f"nesting {c.depth} (max 16)")
    return c.problems


def check_classic(markup: str) -> list[str]:
    c = _check(markup, CLASSIC_TAGS, CLASSIC_ENTITIES, nesting=True)
    text = "".join(c.text)
    if len(text) > 4096:
        c.problems.append(f"{len(text)} characters (max 4096)")
    if not text.strip():
        c.problems.append("empty message")
    return c.problems


def check_keyboard(markup: object) -> list[str]:
    """Inline keyboard rules: a label, exactly one action, callback data of 1–64 bytes, a known
    style, and a numeric icon id."""
    if not isinstance(markup, InlineKeyboardMarkup):
        return []
    problems: list[str] = []
    for row in markup.inline_keyboard:
        if not row:
            problems.append("empty keyboard row")
        for b in row:
            if not b.text.strip():
                problems.append("button without a label")
            actions = [
                x
                for x in (b.callback_data, b.url, b.copy_text, b.disabled, b.web_app, b.login_url)
                if x is not None
            ]
            if len(actions) != 1:
                problems.append(f"button {b.text!r} has {len(actions)} actions")
            if b.callback_data is not None and not 1 <= len(b.callback_data.encode()) <= 64:
                problems.append(f"callback data of {b.text!r} must be 1-64 bytes")
            if b.style not in (None, "danger", "success", "primary"):
                problems.append(f"button style {b.style!r}")
            if b.icon_custom_emoji_id is not None and not b.icon_custom_emoji_id.isdigit():
                problems.append(f"icon id of {b.text!r} isn't numeric")
    return problems
