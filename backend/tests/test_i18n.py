"""In-code i18n button labels."""

from __future__ import annotations

from gozar.bot.i18n import t
from gozar.db.models.enums import Language


def test_labels_per_language() -> None:
    assert t("menu_help", Language.fa) == "❓ راهنما"
    assert t("menu_help", Language.en) == "❓ Help"
    assert t("menu_help", Language.ru) == "❓ Помощь"


def test_unknown_key_returns_key() -> None:
    assert t("does_not_exist", Language.en) == "does_not_exist"
