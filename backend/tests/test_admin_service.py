"""AdminService — stats, user actions, refresh-locations over stub repos/panel + fakeredis."""

from __future__ import annotations

import json

import fakeredis.aioredis

from gozar.cache.redis import sub_cache_key
from gozar.db.models.enums import UserStatus
from gozar.db.models.user import User
from gozar.services.admin import AdminService
from gozar.services.settings_service import SettingKey


class FakeUsers:
    def __init__(
        self,
        user: User | None = None,
        by_status: dict | None = None,
        total: int = 0,
        referrals: int = 0,
    ) -> None:
        self._user = user
        self._by_status = by_status or {}
        self._total = total
        self._referrals = referrals

    async def get(self, telegram_id: int) -> User | None:
        return self._user if self._user and self._user.telegram_id == telegram_id else None

    async def count(self) -> int:
        return self._total

    async def count_by_status(self, status: UserStatus) -> int:
        return self._by_status.get(status, 0)

    async def sum_referrals(self) -> int:
        return self._referrals


class FakeLogs:
    def __init__(self, today: int = 0, for_user: int = 0) -> None:
        self._today = today
        self._for_user = for_user
        self.deleted: list[tuple[int, object]] = []

    async def count_since(self, since: object) -> int:
        return self._today

    async def count_for_user(self, user_id: int) -> int:
        return self._for_user

    async def delete_for_user_since(self, user_id: int, since: object) -> int:
        self.deleted.append((user_id, since))
        return 1


class FakeSettings:
    def __init__(self, values: dict | None = None) -> None:
        self.values = values or {}
        self.sets: list[tuple[str, str]] = []

    async def get(self, key: str) -> str | None:
        return self.values.get(key)

    async def get_int(self, key: str, default: int = 0) -> int:
        value = self.values.get(key)
        return int(value) if value is not None else default

    async def set(self, key: str, value: str) -> None:
        self.sets.append((key, value))
        self.values[key] = value


class FakePanel:
    def __init__(self, panel_user: object = None, locations: list[str] | None = None) -> None:
        self._panel_user = panel_user
        self._locations = locations or []
        self.deleted: list[str] = []

    async def get_user(self, username: str) -> object:
        return self._panel_user

    async def delete_user(self, uuid: str) -> bool:
        self.deleted.append(uuid)
        return True

    async def squad_location_names(self, squad_uuid: str) -> list[str]:
        return list(self._locations)


def _redis() -> fakeredis.aioredis.FakeRedis:
    return fakeredis.aioredis.FakeRedis(decode_responses=True)


def _svc(users=None, logs=None, settings=None, panel=None, redis=None) -> AdminService:
    return AdminService(
        users or FakeUsers(),
        logs or FakeLogs(),
        settings or FakeSettings(),
        panel or FakePanel(),
        redis or _redis(),
    )


async def test_stats_aggregates_counts() -> None:
    users = FakeUsers(
        total=10,
        by_status={
            UserStatus.available: 4,
            UserStatus.active_config: 5,
            UserStatus.banned: 1,
        },
        referrals=12,
    )
    s = await _svc(users=users, logs=FakeLogs(today=3)).stats()
    assert (s.total, s.available, s.active, s.banned, s.configs_today, s.referrals) == (
        10,
        4,
        5,
        1,
        3,
        12,
    )


async def test_ban_revokes_panel_and_flips_status() -> None:
    user = User(telegram_id=5, status=UserStatus.active_config, panel_username="g5_1")
    redis = _redis()
    await redis.set(sub_cache_key(5), "cached")
    panel = FakePanel(panel_user=type("PU", (), {"uuid": "uuid-5"})())
    result = await _svc(users=FakeUsers(user=user), panel=panel, redis=redis).ban(5)
    assert result is user
    assert user.status is UserStatus.banned
    assert user.panel_username is None
    assert panel.deleted == ["uuid-5"]  # live config revoked
    assert await redis.get(sub_cache_key(5)) is None  # cache cleared


async def test_ban_missing_user_returns_none() -> None:
    assert await _svc(users=FakeUsers(user=None)).ban(404) is None


async def test_reclaim_clears_today_and_heals_to_available() -> None:
    user = User(telegram_id=7, status=UserStatus.active_config, panel_username="g7")
    redis = _redis()
    await redis.set(sub_cache_key(7), "cached")
    logs = FakeLogs()
    await _svc(users=FakeUsers(user=user), logs=logs, redis=redis).reclaim(7)
    assert user.status is UserStatus.available
    assert user.panel_username is None
    assert logs.deleted and logs.deleted[0][0] == 7  # rolling claim cooldown cleared
    assert await redis.get(sub_cache_key(7)) is None


async def test_zero_referrals_resets_count() -> None:
    user = User(telegram_id=8, referral_count=9)
    await _svc(users=FakeUsers(user=user)).zero_referrals(8)
    assert user.referral_count == 0


async def test_refresh_locations_writes_allowlist() -> None:
    settings = FakeSettings({SettingKey.TRIAL_SQUAD: "sq1"})
    panel = FakePanel(locations=["NL", "DE"])
    names = await _svc(settings=settings, panel=panel).refresh_locations()
    assert names == ["NL", "DE"]
    assert (SettingKey.LOCATIONS, json.dumps(["NL", "DE"])) in settings.sets


async def test_refresh_locations_without_squad_returns_none() -> None:
    settings = FakeSettings({})  # first-run wizard not done
    assert await _svc(settings=settings).refresh_locations() is None
    assert settings.sets == []
