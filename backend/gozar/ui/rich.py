"""Structured screens for the Telegram admin console: one description, two renderings.

A ``Doc`` collects blocks (heading, paragraph, key/value table, table, folding section, list, check
list, code, footer, button rows). ``rich()`` gives the HTML of a Telegram **rich message** (Bot API
10.1+: ``sendRichMessage`` / ``editMessageText(rich_message=…)`` — tables, ``<details>``, headings,
``<tg-button>``); ``classic()`` gives the same content as a regular ``parse_mode=HTML`` message for
a Telegram app without rich messages (or with them switched off in 🎨), and the buttons that sat
inside the text move to the keyboard (``classic_rows()``).

Every string handed to a Doc is HTML already: the CALLER escapes dynamic values (``esc``). A button
inside a paragraph or a table cell is written with ``inline(Btn(...))`` / ``copy(value)``: a marker
that carries the button itself, so a cell can be built anywhere and rendered either way.

Rich messages are for the operator console only. A user on an old app sees a "not supported"
placeholder instead of one, so every user-facing screen stays a regular message.
"""

from __future__ import annotations

import html
import json
import re
from dataclasses import asdict, dataclass, field

from aiogram.types import CopyTextButton, InlineKeyboardButton

esc = html.escape

#: An in-text button: U+E000 <json> U+E001 (private-use characters no real text carries).
MARK_RX = re.compile("([^]*)")
#: Telegram counts 4096 characters of a regular message AFTER entities are parsed; leave room.
CLASSIC_LIMIT = 4000
#: Rich messages: 32768 characters and 500 blocks (Bot API "Rich message formatting options").
RICH_LIMIT = 32000
RICH_MAX_BLOCKS = 450
TAG_RX = re.compile(r"<[^>]+>")
PRE_RX = re.compile(r"<pre>(.*?)</pre>", re.S)
STYLES = ("success", "danger", "primary")


def visible_len(markup: str) -> int:
    """The length Telegram counts for a regular HTML message (the text without its tags)."""
    return len(html.unescape(TAG_RX.sub("", MARK_RX.sub("", markup))))


@dataclass
class Btn:
    """A button inside the text (rich: ``<tg-button>``; classic: a keyboard button).

    Exactly one of ``copy`` / ``data`` / ``url``. ``style`` is success | danger | primary, or
    "link" (rich only, callback buttons only: drawn as a plain link) — dropped on the keyboard.
    """

    text: str  # plain text, escaped when rendered
    copy: str | None = None  # copies this text to the clipboard
    data: str | None = None  # callback data
    url: str | None = None
    style: str | None = None

    def rich(self) -> str:
        st = f' style="{self.style}"' if self.style else ""
        if self.copy is not None:
            head = f'<tg-button type="copy_text" text="{esc(self.copy)}"{st}>'
        elif self.data is not None:
            head = f'<tg-button type="callback_data" data="{esc(self.data)}"{st}>'
        else:
            head = f'<tg-button type="url" url="{esc(self.url or "")}"{st}>'
        return f"{head}{esc(self.text)}</tg-button>"

    def keyboard(self) -> InlineKeyboardButton:
        st = self.style if self.style in STYLES else None
        if self.copy is not None:  # on the keyboard the button is far from its value: name it
            label = f"{self.text} {self.copy}" if len(self.copy) <= 40 else self.text
            return InlineKeyboardButton(
                text=label, copy_text=CopyTextButton(text=self.copy[:256]), style=st
            )
        if self.data is not None:
            return InlineKeyboardButton(text=self.text, callback_data=self.data, style=st)
        return InlineKeyboardButton(text=self.text, url=self.url, style=st)


def inline(button: Btn) -> str:
    """A button to put inside a paragraph or a table cell."""
    return "" + json.dumps(asdict(button), ensure_ascii=True) + ""


def copy(value: str, label: str = "📑") -> str:
    """A "copy" button right after a value (rich); a keyboard button naming the value (classic)."""
    return inline(Btn(label, copy=value))


def _btn(match: re.Match[str]) -> Btn:
    return Btn(**json.loads(match.group(1)))


@dataclass
class Doc:
    blocks: list[tuple] = field(default_factory=list)

    # ---- building ------------------------------------------------------------------------------
    def h(self, text: str, level: int = 3) -> Doc:
        self.blocks.append(("h", text, max(1, min(level, 6))))
        return self

    def p(self, text: str) -> Doc:
        if text:
            self.blocks.append(("p", text))
        return self

    def text(self, body: str) -> Doc:
        """A regular-message HTML body as content copy is written: paragraphs with their line
        breaks, and ``<pre>`` blocks (escaped there, so unescaped into a code block here)."""
        pos = 0
        for m in PRE_RX.finditer(body):
            self.p(body[pos : m.start()].strip("\n"))
            self.pre(html.unescape(m.group(1)))
            pos = m.end()
        return self.p(body[pos:].strip("\n"))

    def lines(self, lines: list[str]) -> Doc:
        """One paragraph, a line break between the lines."""
        lines = [x for x in lines if x]
        if lines:
            self.blocks.append(("lines", lines))
        return self

    def kv(self, rows: list[tuple[str, str] | None], caption: str = "") -> Doc:
        """A two-column table: label | value. ``None`` rows are skipped."""
        kept = [r for r in rows if r is not None]
        if kept:
            self.blocks.append(("kv", kept, caption))
        return self

    def table(
        self,
        head: list[str] | None,
        rows: list[list[str]],
        *,
        striped: bool = False,
        compact: bool = True,
        caption: str = "",
    ) -> Doc:
        if rows:
            self.blocks.append(("table", head, [list(r) for r in rows], striped, compact, caption))
        return self

    def details(self, summary: str, body: Doc, open: bool = False) -> Doc:  # noqa: A002 (HTML's name)
        if body.blocks:
            self.blocks.append(("details", summary, body, open))
        return self

    def quote(self, text: str, expandable: bool = False) -> Doc:
        if text:
            self.blocks.append(("quote", text, expandable))
        return self

    def items(self, items: list[str]) -> Doc:
        if items:
            self.blocks.append(("ul", list(items)))
        return self

    def checks(self, items: list[tuple[bool, str]]) -> Doc:
        if items:
            self.blocks.append(("checks", list(items)))
        return self

    def pre(self, raw: str) -> Doc:
        """Preformatted text; ``raw`` is NOT HTML (it is escaped here)."""
        if raw:
            self.blocks.append(("pre", raw))
        return self

    def hr(self) -> Doc:
        self.blocks.append(("hr",))
        return self

    def footer(self, text: str) -> Doc:
        if text:
            self.blocks.append(("footer", text))
        return self

    def row(self, buttons: list[Btn], align: str = "center") -> Doc:
        if buttons:
            self.blocks.append(("row", list(buttons), align))
        return self

    def extend(self, other: Doc | None) -> Doc:
        if other is not None:
            self.blocks += other.blocks
        return self

    def __bool__(self) -> bool:
        return bool(self.blocks)

    # ---- rich message --------------------------------------------------------------------------
    def rich(self) -> str:
        out = "".join(self._rich_block(b) for b in self.blocks)
        return MARK_RX.sub(lambda m: _btn(m).rich(), out)

    def _rich_block(self, b: tuple) -> str:
        kind = b[0]
        if kind == "h":
            return f"<h{b[2]}>{b[1]}</h{b[2]}>"
        if kind == "p":  # a newline inside a paragraph is a line break
            return "<p>" + b[1].replace("\n", "<br>") + "</p>"
        if kind == "lines":
            return "<p>" + "<br>".join(b[1]) + "</p>"
        if kind == "kv":
            cap = f"<caption>{b[2]}</caption>" if b[2] else ""
            rows = "".join(f"<tr><th>{k}</th><td>{v}</td></tr>" for k, v in b[1])
            return f"<table bordered compact>{cap}{rows}</table>"
        if kind == "table":
            _, head, rows, striped, compact, caption = b
            attrs = " bordered" + (" striped" if striped else "") + (" compact" if compact else "")
            cap = f"<caption>{caption}</caption>" if caption else ""
            hrow = "<tr>" + "".join(f"<th>{c}</th>" for c in head) + "</tr>" if head else ""
            body = "".join("<tr>" + "".join(f"<td>{c}</td>" for c in r) + "</tr>" for r in rows)
            return f"<table{attrs}>{cap}{hrow}{body}</table>"
        if kind == "details":
            _, summary, body, is_open = b
            inner = "".join(self._rich_block(x) for x in body.blocks)
            attr = " open" if is_open else ""
            return f"<details{attr}><summary>{summary}</summary>{inner}</details>"
        if kind == "quote":
            text = b[1].replace("\n", "<br>")
            tag = "blockquote expandable" if b[2] else "blockquote"
            return f"<{tag}>{text}</blockquote>"
        if kind == "ul":
            return "<ul>" + "".join(f"<li>{x}</li>" for x in b[1]) + "</ul>"
        if kind == "checks":
            items = "".join(
                f'<li><input type="checkbox"{" checked" if c else ""}>{x}</li>' for c, x in b[1]
            )
            return f"<ul>{items}</ul>"
        if kind == "pre":
            return f"<pre>{esc(b[1])}</pre>"
        if kind == "hr":
            return "<hr/>"
        if kind == "footer":
            return "<footer>" + b[1].replace("\n", "<br>") + "</footer>"
        if kind == "row":
            buttons = "".join(x.rich() for x in b[1])
            return f'<tg-button-row align="{b[2]}">{buttons}</tg-button-row>'
        raise ValueError(kind)

    def fits_rich(self) -> bool:
        """Within the rich message limits (characters, blocks) — else send the classic one."""
        return len(self.rich()) <= RICH_LIMIT and self._count() <= RICH_MAX_BLOCKS

    def _count(self) -> int:
        n = 0
        for b in self.blocks:
            n += 1
            if b[0] == "details":
                n += b[2]._count()
            elif b[0] in ("kv", "table"):
                n += len(b[1] if b[0] == "kv" else b[2])
        return n

    # ---- regular message -----------------------------------------------------------------------
    def classic(self, limit: int = CLASSIC_LIMIT) -> str:
        parts = [
            p for p in (self._classic_block(b, quoted=False) for b in self.blocks) if p is not None
        ]
        if visible_len("\n".join(parts)) > limit:  # drop whole blocks from the end: never cut a tag
            while parts and visible_len("\n".join([*parts, "…"])) > limit:
                parts.pop()
            parts.append("…")
        return MARK_RX.sub("", "\n".join(parts)).strip()

    def _classic_block(self, b: tuple, quoted: bool) -> str | None:
        kind = b[0]
        if kind == "h":
            return f"<b>{b[1]}</b>" if b[2] <= 2 else f"\n<b>{b[1]}</b>"
        if kind == "p":
            return b[1]
        if kind == "lines":
            return "\n".join(b[1])
        if kind == "kv":
            cap = [f"<i>{b[2]}</i>"] if b[2] else []
            return "\n".join(cap + [f"{k}: {v}" for k, v in b[1]])
        if kind == "table":
            _, head, rows, _striped, _compact, caption = b
            out = [f"<i>{caption}</i>"] if caption else []
            if head:
                out.append("<b>" + " | ".join(head) + "</b>")
            out += ["• " + " | ".join(c for c in r if c) for r in rows]
            return "\n".join(out)
        if kind == "details":
            _, summary, body, is_open = b
            inside = quoted or not is_open
            inner = "\n".join(
                x
                for x in (self._classic_block(y, quoted=inside) for y in body.blocks)
                if x is not None
            )
            if not inside or quoted:
                return f"\n<b>{summary}</b>\n{inner}"
            return f"<blockquote expandable><b>{summary}</b>\n{inner}</blockquote>"
        if kind == "quote":
            if quoted:
                return b[1]
            tag = "blockquote expandable" if b[2] else "blockquote"
            return f"<{tag}>{b[1]}</blockquote>"
        if kind == "ul":
            return "\n".join(f"• {x}" for x in b[1])
        if kind == "checks":
            return "\n".join(f"{'☑️' if c else '⬜️'} {x}" for c, x in b[1])
        if kind == "pre":
            return f"<code>{esc(b[1])}</code>" if quoted else f"<pre>{esc(b[1])}</pre>"
        if kind == "hr":
            return ""
        if kind == "footer":
            return f"<i>{b[1]}</i>"
        if kind == "row":
            return None
        raise ValueError(kind)

    def classic_rows(self) -> list[list[InlineKeyboardButton]]:
        """Keyboard rows for the in-text buttons and button blocks (classic rendering only)."""
        rows: list[list[InlineKeyboardButton]] = []
        seen: set[str] = set()

        def strings(x: object):
            if isinstance(x, str):
                yield x
            elif isinstance(x, list | tuple):
                for y in x:
                    yield from strings(y)

        def walk(blocks: list[tuple]) -> None:
            for b in blocks:
                if b[0] == "row":
                    rows.append([x.keyboard() for x in b[1]])
                    continue
                found = (
                    MARK_RX.finditer(b[1])
                    if b[0] == "details"
                    else (m for s in strings(b) for m in MARK_RX.finditer(s))
                )
                for m in found:
                    if m.group(1) not in seen:
                        seen.add(m.group(1))
                        rows.append([_btn(m).keyboard()])
                if b[0] == "details":
                    walk(b[2].blocks)

        walk(self.blocks)
        return rows


def as_doc(content: Doc | str) -> Doc:
    """A plain HTML string as a Doc (paragraphs + code blocks), so a prompt can go out rich too."""
    return content if isinstance(content, Doc) else Doc().text(content)
