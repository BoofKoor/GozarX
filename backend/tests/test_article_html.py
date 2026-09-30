"""Landing bodies reach the public site sanitised: the site shares the panel's origin (and its
admin tokens), so a handler in a pasted body used to run for every visitor."""

from __future__ import annotations

import re

import pytest

from gozar.seed_landings import DEFAULT_SITE_LANDINGS
from gozar.services.article_html import sanitize_article_html

ALLOWED = set("p br h2 h3 h4 ul ol li strong b em i blockquote code pre hr small a".split())


@pytest.mark.parametrize(
    "evil",
    [
        "<img src=x onerror=alert(1)>",
        "<script>alert(1)</script>",
        '<a href="javascript:alert(1)">x</a>',
        '<a href="//evil.example">x</a>',
        '<a href="/\\evil.example">x</a>',
        # The URL parser drops a tab or newline anywhere: `/<TAB>/evil` is followed as `//evil`.
        '<a href="/\t/evil.example">x</a>',
        '<a href="/\n/evil.example">x</a>',
        '<a href="https://ok.example\t@evil.example">x</a>',
        '<p onclick="alert(1)">x</p>',
        "<svg onload=alert(1)>",
    ],
)
def test_nothing_executable_survives(evil: str) -> None:
    out = sanitize_article_html(evil)
    # Every REAL tag left in the output is a bare allowlisted one or a vetted link; everything else
    # was escaped into visible text.
    for name, attrs in re.findall(r"<(/?[A-Za-z][\w-]*)([^>]*)>", out):
        assert name.lstrip("/").lower() in ALLOWED, (name, out)
        if attrs.strip():
            href = re.fullmatch(r'\s+href="([^"]*)"(?: target="_blank" rel="[^"]*")?', attrs)
            assert href is not None, (attrs, out)
            target = href.group(1)
            assert not re.search(r"[\s\x00-\x1f\x7f]", target), out
            assert target.startswith(("https://", "http://")) or (
                target.startswith("/") and not target.startswith("//") and "\\" not in target
            ), out


def test_links_are_kept_in_site_and_opened_safely_off_site() -> None:
    out = sanitize_article_html('<a href="/locations">L</a> <a href="https://t.me/x">T</a>')
    assert '<a href="/locations">L</a>' in out
    external = '<a href="https://t.me/x" target="_blank" rel="noopener noreferrer nofollow">'
    assert external + "T</a>" in out


def test_every_default_landing_renders_unchanged() -> None:
    # The allowlist must not visibly break the copy the site ships with.
    for landing in DEFAULT_SITE_LANDINGS:
        body = landing["body"] or ""
        assert sanitize_article_html(body) == body, landing["slug"]
