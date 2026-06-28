"""Pure {token} rendering — substitutes only provided tokens, never str.replace."""

from __future__ import annotations

from gozar.services.content import render, sanitize_tokens

# Invisible marks that creep into {token} when editing Latin tokens amid RTL Persian.
RLM = "‏"
ZWNJ = "‌"


def test_render_substitutes_provided() -> None:
    assert render("Hi {name}, {n} left", {"name": "Ali", "n": 3}) == "Hi Ali, 3 left"


def test_render_leaves_unprovided_intact() -> None:
    assert render("Hi {name}, {missing}", {"name": "Ali"}) == "Hi Ali, {missing}"


def test_render_no_tokens() -> None:
    assert render("plain text", {}) == "plain text"


def test_render_repeated_token() -> None:
    assert render("{x}-{x}", {"x": "1"}) == "1-1"


def test_render_tolerates_bidi_marks_inside_braces() -> None:
    # the live {referrals} bug: a hidden RLM inside the braces — must still substitute
    assert render(f"دعوت: {{referrals{RLM}}}", {"referrals": 7}) == "دعوت: 7"
    assert render(f"دعوت: {{{RLM}referrals}}", {"referrals": 7}) == "دعوت: 7"


def test_render_does_not_touch_meaningful_zwnj_in_prose() -> None:
    # ZWNJ inside ordinary Persian (می‌خواهم) must survive — we only clean inside token candidates
    out = render(f"می{ZWNJ}خواهم {{name}}", {"name": "X"})
    assert out == f"می{ZWNJ}خواهم X" and ZWNJ in out


def test_render_non_token_braces_stay_literal() -> None:
    assert render("a {free text} b", {}) == "a {free text} b"
    assert render("{}", {}) == "{}"


def test_sanitize_tokens_cleans_contaminated_keys() -> None:
    assert sanitize_tokens(f"x {{referrals{RLM}}} y") == "x {referrals} y"
    # non-identifier candidates + meaningful prose ZWNJ are left untouched
    assert sanitize_tokens("a {free text} b") == "a {free text} b"
    assert sanitize_tokens(f"می{ZWNJ}خواهم") == f"می{ZWNJ}خواهم"


async def test_message_carries_link_preview_flag() -> None:
    import json

    import fakeredis.aioredis

    from gozar.db.models.enums import Language
    from gozar.services.content import ContentService

    redis = fakeredis.aioredis.FakeRedis(decode_responses=True)
    # new cache format: body + link-preview flag
    await redis.set("cache:content:fa:apps", json.dumps({"b": "get {app}", "lp": False}))
    await redis.set("cache:content:fa:welcome", json.dumps({"b": "hi", "lp": True}))
    # legacy plain-string cache entry → preview defaults on (back-compat)
    await redis.set("cache:content:fa:legacy", "old body")
    svc = ContentService(None, redis)  # type: ignore[arg-type]  # session unused on cache hits

    apps = await svc.message("apps", Language.fa, app="X")
    assert apps.text == "get X" and apps.link_preview is False
    assert (await svc.message("welcome", Language.fa)).link_preview is True
    assert (await svc.message("legacy", Language.fa)).link_preview is True
