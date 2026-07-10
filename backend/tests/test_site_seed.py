"""Seed: the ``site_*`` settings + content are inserted as defaults, idempotently, and never clobber
admin edits — and the wizard-picked ``site_trial_squad`` / ``site_locations`` are NOT seeded.

DB-gated (uses the ``session`` fixture). Exercises the exact ``add_default`` loops the seed runs.
"""

from __future__ import annotations

from sqlalchemy import func, select

from gozar.db.models.content import Content
from gozar.db.models.setting import Setting
from gozar.db.repositories.content import ContentRepository
from gozar.db.repositories.settings import SettingsRepository
from gozar.seed import DEFAULT_SITE_CONTENT, DEFAULT_SITE_SETTINGS
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
