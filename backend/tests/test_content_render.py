"""Pure {token} rendering — substitutes only provided tokens, never str.replace."""

from __future__ import annotations

from gozar.services.content import render


def test_render_substitutes_provided() -> None:
    assert render("Hi {name}, {n} left", {"name": "Ali", "n": 3}) == "Hi Ali, 3 left"


def test_render_leaves_unprovided_intact() -> None:
    assert render("Hi {name}, {missing}", {"name": "Ali"}) == "Hi Ali, {missing}"


def test_render_no_tokens() -> None:
    assert render("plain text", {}) == "plain text"


def test_render_repeated_token() -> None:
    assert render("{x}-{x}", {"x": "1"}) == "1-1"
