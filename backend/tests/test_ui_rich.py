"""The console's Doc: one description, a rich rendering and a regular one, both valid Telegram
markup — and the regular one never loses an in-text button (it moves to the keyboard)."""

from __future__ import annotations

from gozar.db.models.enums import Language
from gozar.ui import fmt
from gozar.ui.rich import Btn, Doc, copy, inline, visible_len
from gozar.ui.validate import check_classic, check_keyboard, check_rich


def _sample() -> Doc:
    doc = Doc().h("🛠 Title", 2)
    doc.kv([("Users", "12"), None, ("Server", f"<code>1.2.3.4</code> {copy('1.2.3.4', '📑')}")])
    doc.table(["A", "B"], [["1", "2"], ["3", inline(Btn("go", data="admin:menu"))]], caption="cap")
    doc.details("more", Doc().p("hidden line").pre("raw <b> stays text"))
    doc.quote("a note", expandable=True)
    doc.checks([(True, "done"), (False, "todo")])
    doc.footer("foot")
    doc.row([Btn("ok", data="admin:look", style="success"), Btn("site", url="https://e.x")])
    return doc


def test_rich_rendering_is_valid_rich_html() -> None:
    html = _sample().rich()
    assert check_rich(html) == []
    assert "<table bordered compact>" in html
    assert '<tg-button type="copy_text" text="1.2.3.4">📑</tg-button>' in html
    assert '<tg-button type="callback_data" data="admin:menu">go</tg-button>' in html
    assert '<tg-button-row align="center">' in html
    assert "<details><summary>more</summary>" in html
    assert '<input type="checkbox" checked>' in html


def test_classic_rendering_is_valid_and_moves_in_text_buttons_to_the_keyboard() -> None:
    doc = _sample()
    text = doc.classic()
    assert check_classic(text) == []
    assert "" not in text and "tg-button" not in text  # no marker or rich tag left
    assert "Users: 12" in text
    assert "<blockquote expandable><b>more</b>" in text  # a closed section folds
    assert "&lt;b&gt; stays text" in text
    rows = doc.classic_rows()
    labels = [[b.text for b in row] for row in rows]
    assert ["📑 1.2.3.4"] in labels  # a copy button names its value away from it
    assert ["go"] in labels
    assert ["ok", "site"] in labels  # a button row keeps its row
    from aiogram.types import InlineKeyboardMarkup

    assert check_keyboard(InlineKeyboardMarkup(inline_keyboard=rows)) == []


def test_classic_cuts_whole_blocks_never_inside_a_tag() -> None:
    doc = Doc()
    for i in range(400):
        doc.p(f"<b>line {i}</b> " + "x" * 20)
    text = doc.classic()
    assert visible_len(text) <= 4000
    assert text.endswith("…")
    assert check_classic(text) == []


def test_a_doc_over_the_rich_limits_is_sent_as_a_regular_message() -> None:
    small, big = Doc().p("hi"), Doc()
    for _ in range(600):
        big.p("x")
    assert small.fits_rich() and not big.fits_rich()


def test_text_turns_a_content_body_into_paragraphs_and_code() -> None:
    doc = Doc().text("first\nsecond<pre>a &lt; b</pre>tail")
    assert doc.blocks == [("p", "first\nsecond"), ("pre", "a < b"), ("p", "tail")]
    assert check_rich(doc.rich()) == []


def test_times_and_numbers_render_valid_markup_in_both_renderings() -> None:
    from datetime import UTC, datetime

    moment = datetime(2026, 10, 19, 10, 30, tzinfo=UTC)
    cell = fmt.when(moment, Language.fa)
    assert 'unix="1792405800"' in cell and 'format="dt"' in cell
    assert "۱۴:۰۰" in cell  # the fallback is the Tehran clock, in Persian digits
    doc = Doc().kv(
        [("t", cell), ("n", fmt.num(1234567, Language.fa)), ("r", fmt.ago(moment, Language.en))]
    )
    assert check_rich(doc.rich()) == [] and check_classic(doc.classic()) == []
    assert fmt.num(1234567, Language.fa) == "۱٬۲۳۴٬۵۶۷"
    assert fmt.num(1234567, Language.en) == "1,234,567"
    assert fmt.num(None, Language.fa) == "—"
    assert fmt.pct(1, 0, Language.en) == "—"  # a share of nobody is unknown, not 0%
