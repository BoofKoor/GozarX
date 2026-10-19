"""Every console screen is valid Telegram markup — rich, regular, and its keyboard — in all three
languages, drawn plain and with premium icons (``ui/validate`` mirrors Telegram's own rules)."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from gozar.bot import screens
from gozar.bot.handlers.admin.locations import locations_doc, locations_keyboard
from gozar.bot.handlers.admin.look import _sample_doc, look_keyboard
from gozar.bot.handlers.admin.stats import stats_doc
from gozar.bot.handlers.admin.users import card_doc
from gozar.bot.keyboards import admin_menu_keyboard, admin_user_card_keyboard
from gozar.db.models.config_log import ConfigLog
from gozar.db.models.enums import Language, UserStatus
from gozar.db.models.user import User
from gozar.services.admin import AdminStats, ConsoleStats, LocationOverview, UserCard
from gozar.ui.buttons import EMPTY_OVERRIDES
from gozar.ui.console_text import TEXT, tr
from gozar.ui.look import PLAIN, Look
from gozar.ui.validate import check_classic, check_keyboard, check_rich

LANGS = (Language.fa, Language.en, Language.ru)
NOW = datetime(2026, 10, 19, 12, 0, tzinfo=UTC)


def _stats() -> ConsoleStats:
    return ConsoleStats(
        totals=AdminStats(
            total=1200, available=800, active=350, banned=50, configs_today=90, referrals=400
        ),
        new_today=12,
        active_users_today=85,
        week=[(f"2026-10-{d:02d}", d * 3, d) for d in range(13, 20)],
        locations=[("🇩🇪 آلمان", 40), ("هلند", 30), ("WARP <1>", 2)],
        locations_total=5,
        top_referrers=[(111, 9), (222, 4)],
    )


def _card() -> UserCard:
    user = User(
        telegram_id=777,
        language=Language.fa,
        status=UserStatus.active_config,
        referral_count=3,
        panel_username="g_777_x",
        created_at=NOW,
        unreachable_at=NOW,
    )
    logs = tuple(
        ConfigLog(user_id=777, location=loc, created_at=NOW) for loc in ("🇩🇪 آلمان", "هلند")
    )
    return UserCard(user=user, configs=12, recent=logs)


def _overview(**kw: object) -> LocationOverview:
    base = {
        "squad_uuid": "sq-1",
        "squad_name": "Trial",
        "names": ["🇩🇪 آلمان", "هلند", "Finland 🇫🇮"],
        "offered": ["🇩🇪 آلمان", "هلند"],
        "allow": ["🇩🇪 آلمان", "هلند"],
        "today": {"هلند": 4},
    }
    base.update(kw)
    return LocationOverview(**base)  # type: ignore[arg-type]


def _docs(lang: Language):
    yield stats_doc(_stats(), lang)
    yield card_doc(_card(), lang, note="⛔️ done")
    yield locations_doc(_overview(), lang, note="refreshed")
    yield locations_doc(_overview(names=None), lang)
    yield locations_doc(_overview(squad_uuid=None), lang)
    yield locations_doc(_overview(names=[], offered=[]), lang)
    yield _sample_doc(lang)


@pytest.mark.parametrize("lang", LANGS)
@pytest.mark.parametrize("look", [PLAIN, Look()])
def test_every_console_screen_is_valid_markup(lang: Language, look: Look) -> None:
    for doc in _docs(lang):
        for v in screens.variants(doc, None, look):
            problems = check_rich(v.body) if v.rich else check_classic(v.body)
            assert problems == [], (lang, v.rich, v.themed, problems, v.body[:200])
            assert check_keyboard(v.markup) == []


@pytest.mark.parametrize("lang", LANGS)
def test_console_keyboards_are_valid(lang: Language) -> None:
    for markup in (
        admin_menu_keyboard(lang, EMPTY_OVERRIDES),
        admin_user_card_keyboard(lang, banned=True),
        locations_keyboard(lang, EMPTY_OVERRIDES, refresh=True),
        look_keyboard(Look(), lang, EMPTY_OVERRIDES, blocked=True),
    ):
        for v in screens.variants("x", markup, Look()):
            assert check_keyboard(v.markup) == []


def test_a_subset_of_locations_says_what_it_hid() -> None:
    text = locations_doc(_overview(), Language.en).classic()
    assert "Only the locations picked in the web panel are offered (2 of 3)" in text
    assert "WARP" not in text
    every = locations_doc(_overview(offered=["a", "b", "c"], allow=[]), Language.en).classic()
    assert "a host added later appears by itself" in every


def test_the_stats_screen_names_what_its_capped_list_hid_and_escapes_remarks() -> None:
    text = stats_doc(_stats(), Language.en).classic()
    assert "and 2 more" in text
    assert "WARP &lt;1&gt;" in text


def test_every_console_text_has_persian_and_fills_its_fields() -> None:
    for key, texts in TEXT.items():
        assert texts.get(Language.fa), key
    assert tr("home_users_val", Language.en, total="5", new="1") == "5 • today +1"
    assert tr("no_such_key", Language.en) == "no_such_key"
