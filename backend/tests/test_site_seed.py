"""Seed: the ``site_*`` settings + content are inserted as defaults, idempotently, and never clobber
admin edits — and the wizard-picked ``site_trial_squad`` / ``site_locations`` are NOT seeded.

DB-gated (uses the ``session`` fixture). Exercises the exact ``add_default`` loops the seed runs.
"""

from __future__ import annotations

from sqlalchemy import func, select

from gozar.db.models.content import Content
from gozar.db.models.enums import Language
from gozar.db.models.setting import Setting
from gozar.db.repositories.content import ContentRepository
from gozar.db.repositories.settings import SettingsRepository
from gozar.db.repositories.site_faq_item import SiteFaqItemRepository
from gozar.db.repositories.site_landing_page import SiteLandingPageRepository
from gozar.seed import (
    DEFAULT_SITE_CONTENT,
    DEFAULT_SITE_SETTINGS,
    FAQ_SEEDED,
    LANDINGS_SEEDED,
    seed_defaults,
)
from gozar.seed_faq import DEFAULT_SITE_FAQ
from gozar.seed_landings import DEFAULT_SITE_LANDINGS
from gozar.services.settings_service import SiteSettingKey

_EXPECTED_CONTENT_ROWS = sum(len(bodies) for bodies in DEFAULT_SITE_CONTENT.values())


async def _seed_site(session) -> None:
    settings_repo = SettingsRepository(session)
    content_repo = ContentRepository(session)
    for key, value in DEFAULT_SITE_SETTINGS.items():
        await settings_repo.add_default(key, value)
    for key, bodies in DEFAULT_SITE_CONTENT.items():
        for lang, body in bodies.items():
            await content_repo.add_default(key, lang, body)
    await session.flush()


async def test_site_settings_seeded(session) -> None:
    await _seed_site(session)
    for key, value in DEFAULT_SITE_SETTINGS.items():
        row = await session.get(Setting, key)
        assert row is not None and row.value == value


async def test_seed_is_idempotent(session) -> None:
    await _seed_site(session)
    await _seed_site(session)  # a second boot must not duplicate or change anything
    settings_count = await session.scalar(
        select(func.count()).select_from(Setting).where(Setting.key.like("site\\_%", escape="\\"))
    )
    content_count = await session.scalar(
        select(func.count()).select_from(Content).where(Content.key.like("site\\_%", escape="\\"))
    )
    assert settings_count == len(DEFAULT_SITE_SETTINGS)
    assert content_count == _EXPECTED_CONTENT_ROWS


async def test_wizard_keys_not_seeded(session) -> None:
    await _seed_site(session)
    assert await session.get(Setting, SiteSettingKey.SITE_TRIAL_SQUAD) is None
    assert await session.get(Setting, SiteSettingKey.SITE_LOCATIONS) is None


async def test_add_default_never_clobbers_admin_edit(session) -> None:
    settings_repo = SettingsRepository(session)
    await settings_repo.set(SiteSettingKey.SITE_DAILY_LIMIT_MB, "4096")  # admin changed it
    await session.flush()
    await _seed_site(session)  # a later boot re-seeds defaults
    row = await session.get(Setting, SiteSettingKey.SITE_DAILY_LIMIT_MB)
    assert row is not None and row.value == "4096"  # untouched


async def test_site_content_is_bilingual_only(session) -> None:
    """Site copy is fa/en — never the bot's ru — so the two content namespaces stay disjoint."""
    langs = {lang.value for bodies in DEFAULT_SITE_CONTENT.values() for lang in bodies}
    assert langs == {"fa", "en"}


async def test_a_blank_seeded_row_is_restored_but_an_edit_is_not(session) -> None:
    """An older site-copy editor's reset stored "" — the seed puts the default back, and ONLY there.

    A blank push title has nothing behind it: the nudge rendered as ``[site_push_expired_title]``.
    """
    repo = ContentRepository(session)
    await repo.upsert("site_push_expired_title", Language.fa, "  ")
    await repo.upsert("site_hero_title", Language.fa, "عنوان من")
    await session.flush()

    restored = await repo.restore_blank(
        "site_push_expired_title",
        Language.fa,
        DEFAULT_SITE_CONTENT["site_push_expired_title"][Language.fa],
    )
    untouched = await repo.restore_blank(
        "site_hero_title", Language.fa, DEFAULT_SITE_CONTENT["site_hero_title"][Language.fa]
    )
    await session.flush()

    assert restored is True and untouched is False
    assert (
        await repo.get_body("site_push_expired_title", Language.fa)
        == (DEFAULT_SITE_CONTENT["site_push_expired_title"][Language.fa])
    )
    assert await repo.get_body("site_hero_title", Language.fa) == "عنوان من"


async def test_faq_and_landings_are_seeded_once_and_stay_deleted(session) -> None:
    """A default the operator deleted used to come back on the next boot (16 → 15 → 16)."""
    await seed_defaults(session)
    await session.flush()
    faq = SiteFaqItemRepository(session)
    landings = SiteLandingPageRepository(session)
    assert len(await faq.list()) == len(DEFAULT_SITE_FAQ)
    assert len(await landings.list()) == len(DEFAULT_SITE_LANDINGS)

    await faq.delete((await faq.list())[0])
    await landings.delete((await landings.list())[0])
    await session.flush()
    await seed_defaults(session)  # the next boot
    await session.flush()

    assert len(await faq.list()) == len(DEFAULT_SITE_FAQ) - 1
    assert len(await landings.list()) == len(DEFAULT_SITE_LANDINGS) - 1


async def test_an_install_seeded_by_an_older_build_only_gains_the_marker(session) -> None:
    # No marker yet, but rows exist: an older build seeded them, and what is left is the operator's.
    faq = SiteFaqItemRepository(session)
    await faq.add_default(**DEFAULT_SITE_FAQ[0])  # type: ignore[arg-type]
    await session.flush()

    await seed_defaults(session)
    await session.flush()

    assert len(await faq.list()) == 1
    assert await SettingsRepository(session).get(FAQ_SEEDED) == "1"
    assert await SettingsRepository(session).get(LANDINGS_SEEDED) == "1"


async def test_a_reworded_default_question_is_not_duplicated(session) -> None:
    await seed_defaults(session)
    await session.flush()
    faq = SiteFaqItemRepository(session)
    item = (await faq.list())[0]
    await faq.update(
        item,
        locale=item.locale,
        category=item.category,
        question="سؤالی که بازنویسی شد",
        answer=item.answer,
        position=item.position,
        published=item.published,
    )
    await session.flush()

    await seed_defaults(session)
    await session.flush()

    # Keyed on (locale, question), the original wording used to be re-inserted beside the edit.
    assert len(await faq.list()) == len(DEFAULT_SITE_FAQ)
