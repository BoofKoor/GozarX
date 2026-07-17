"""Gating for the Persian-only promo button (``_ad_button``) on the delivered-config screen.

Pure logic — a tiny stand-in for ``SettingsService`` exposing only the two accessors the helper
uses, so this needs neither Redis nor a database.
"""

from __future__ import annotations

import pytest

from gozar.bot.handlers.config import _ad_button
from gozar.bot.keyboards import AdButton
from gozar.db.models.enums import Language
from gozar.services.settings_service import SettingKey

_TRUE = {"1", "true", "yes", "on"}


class _FakeSettings:
    def __init__(self, values: dict[str, str]) -> None:
        self._v = values

    async def get(self, key: str) -> str | None:
        return self._v.get(key)

    async def get_bool(self, key: str, default: bool = False) -> bool:
        raw = self._v.get(key)
        if raw is None or raw.strip() == "":
            return default
        return raw.strip().lower() in _TRUE


def _cfg(**over: str) -> _FakeSettings:
    base = {
        SettingKey.AD_BUTTON_ENABLED: "true",
        SettingKey.AD_BUTTON_TEXT: "کانال ما",
        SettingKey.AD_BUTTON_URL: "https://t.me/example",
        SettingKey.AD_BUTTON_EMOJI_ID: "",
    }
    base.update(over)
    return _FakeSettings(base)


async def test_ad_button_enabled_fa_returns_button() -> None:
    ad = await _ad_button(_cfg(), Language.fa)
    assert ad == AdButton(text="کانال ما", url="https://t.me/example", emoji_id=None)


async def test_ad_button_carries_optional_emoji() -> None:
    cfg = _cfg(**{SettingKey.AD_BUTTON_EMOJI_ID: "5368324170671202286"})
    ad = await _ad_button(cfg, Language.fa)
    assert ad is not None and ad.emoji_id == "5368324170671202286"


@pytest.mark.parametrize("lang", [Language.en, Language.ru])
async def test_ad_button_is_persian_only(lang: Language) -> None:
    assert await _ad_button(_cfg(), lang) is None


async def test_ad_button_hidden_when_disabled() -> None:
    assert await _ad_button(_cfg(**{SettingKey.AD_BUTTON_ENABLED: "false"}), Language.fa) is None


async def test_ad_button_hidden_when_text_missing() -> None:
    assert await _ad_button(_cfg(**{SettingKey.AD_BUTTON_TEXT: "   "}), Language.fa) is None


async def test_ad_button_rejects_non_button_url() -> None:
    # A blank or non-http(s)/tg link would be rejected by Telegram on send — gate it out up front.
    for bad in ("", "example.com", "javascript:alert(1)"):
        cfg = _cfg(**{SettingKey.AD_BUTTON_URL: bad})
        assert await _ad_button(cfg, Language.fa) is None


async def test_ad_button_allows_tg_scheme() -> None:
    cfg = _cfg(**{SettingKey.AD_BUTTON_URL: "tg://resolve?domain=example"})
    ad = await _ad_button(cfg, Language.fa)
    assert ad is not None and ad.url.startswith("tg://")
