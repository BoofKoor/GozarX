"""Phase 1 repository integration tests (skipped unless TEST_DATABASE_URL is set)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from gozar.db.models.enums import Language, UserStatus
from gozar.db.repositories.config_log import ConfigLogRepository
from gozar.db.repositories.content import ContentRepository
from gozar.db.repositories.settings import SettingsRepository
from gozar.db.repositories.user import UserRepository


async def test_user_get_or_create(session) -> None:
    repo = UserRepository(session)
    user, created = await repo.get_or_create(111, language=Language.en)
    assert created is True
    assert user.telegram_id == 111
    assert user.language is Language.en
    assert user.status is UserStatus.available  # column default
    assert user.referral_count == 0
    assert user.reminder_enabled is True

    same, created_again = await repo.get_or_create(111)
    assert created_again is False
    assert same.telegram_id == 111
    assert await repo.count() == 1


async def test_config_log_counts(session) -> None:
    await UserRepository(session).create(222)
    logs = ConfigLogRepository(session)
    await logs.add(222, "Germany")
    await logs.add(222, "Finland")

    assert await logs.count_for_user(222) == 2
    assert await logs.count_for_user_since(222, datetime.now(UTC) + timedelta(hours=1)) == 0
    assert await logs.count_for_user_since(222, datetime.now(UTC) - timedelta(hours=1)) == 2


async def test_content_upsert(session) -> None:
    repo = ContentRepository(session)
    await repo.upsert("welcome", Language.fa, "first")
    assert await repo.get_body("welcome", Language.fa) == "first"

    await repo.upsert("welcome", Language.fa, "second")  # conflict -> update
    assert await repo.get_body("welcome", Language.fa) == "second"
    assert await repo.get_body("welcome", Language.en) is None
    assert len(await repo.all()) == 1


async def test_settings_upsert(session) -> None:
    repo = SettingsRepository(session)
    await repo.set("daily_limit_mb", "500")
    assert await repo.get("daily_limit_mb") == "500"

    await repo.set("daily_limit_mb", "750")  # conflict -> update
    assert await repo.get("daily_limit_mb") == "750"
    assert await repo.all_as_dict() == {"daily_limit_mb": "750"}
    assert await repo.get("missing") is None
