"""ReferralService: same-session atomic +1, capped bonus, live uuid bump, and the skip cases.

DB-gated (real session + repos) with fakeredis-backed settings and a ``FakePanel`` stub.
"""

from __future__ import annotations

import json
import os

import fakeredis.aioredis
import pytest

from gozar.cache.redis import SETTINGS_KEY
from gozar.db.models.enums import UserStatus
from gozar.db.models.user import User
from gozar.db.repositories.config_log import ConfigLogRepository
from gozar.db.repositories.user import UserRepository
from gozar.remnawave.schemas import PanelUser
from gozar.services.referral import ReferralService
from gozar.services.settings_service import SettingKey, SettingsService

pytestmark = pytest.mark.skipif(
    not os.environ.get("TEST_DATABASE_URL"), reason="TEST_DATABASE_URL not set"
)

_SETTINGS = {
    SettingKey.DAILY_LIMIT_MB: "1024",
    SettingKey.REFERRAL_REWARD_MB: "500",
    SettingKey.REFERRAL_REWARD_LIMIT: "10",
}


class FakePanel:
    def __init__(self, user: PanelUser | None = None) -> None:
        self._user = user
        self.traffic_updates: list[tuple[str, int]] = []

    async def get_user(self, username: str) -> PanelUser | None:
        return self._user

    async def update_traffic_limit(self, uuid: str, traffic_bytes: int) -> PanelUser:
        self.traffic_updates.append((uuid, traffic_bytes))
        return PanelUser(uuid=uuid)


async def _service(session, panel) -> ReferralService:
    redis = fakeredis.aioredis.FakeRedis(decode_responses=True)
    await redis.set(SETTINGS_KEY, json.dumps(_SETTINGS))
    return ReferralService(UserRepository(session), SettingsService(session, redis), panel)


async def _add(session, **kw) -> User:
    user = User(**kw)
    session.add(user)
    await session.flush()
    return user


async def test_award_increments_and_persists_atomically(session) -> None:
    await _add(session, telegram_id=1, status=UserStatus.available, referral_count=0)
    invitee = await _add(session, telegram_id=2, referred_by=1)
    referral = await _service(session, FakePanel())
    await ConfigLogRepository(session).add(invitee.telegram_id, "Germany")  # the first claim row

    award = await referral.award_first_claim(invitee)

    assert award is not None and award.new_count == 1
    await session.commit()
    session.expire_all()  # force a fresh DB read to prove durability
    reloaded = await UserRepository(session).get(1)
    assert reloaded.referral_count == 1  # +1 landed in the SAME commit as the config_log
    assert await ConfigLogRepository(session).count_for_user(2) == 1


async def test_award_bumps_live_inviter_trial_by_uuid(session) -> None:
    panel = FakePanel(PanelUser(uuid="u-inv"))
    await _add(
        session,
        telegram_id=1,
        status=UserStatus.active_config,
        panel_username="g1_live",
        referral_count=2,
    )
    invitee = await _add(session, telegram_id=2, referred_by=1)
    referral = await _service(session, panel)

    award = await referral.award_first_claim(invitee)

    assert award.new_count == 3
    expected = (1024 + 3 * 500) * 1024 * 1024  # within the cap of 10
    assert panel.traffic_updates == [("u-inv", expected)]  # PATCH keyed off the uuid
    assert award.new_daily_bytes == expected


async def test_award_caps_the_bonus(session) -> None:
    await _add(session, telegram_id=1, status=UserStatus.available, referral_count=15)
    invitee = await _add(session, telegram_id=2, referred_by=1)
    referral = await _service(session, FakePanel())

    award = await referral.award_first_claim(invitee)

    assert award.new_count == 16
    assert award.new_daily_bytes == (1024 + 10 * 500) * 1024 * 1024  # capped at 10 referrals


async def test_award_inactive_inviter_no_panel_call(session) -> None:
    panel = FakePanel(PanelUser(uuid="u-inv"))
    await _add(session, telegram_id=1, status=UserStatus.available, panel_username=None)
    invitee = await _add(session, telegram_id=2, referred_by=1)

    await (await _service(session, panel)).award_first_claim(invitee)
    assert panel.traffic_updates == []  # not active -> no live bump


async def test_award_skips_without_referrer(session) -> None:
    invitee = await _add(session, telegram_id=2, referred_by=None)
    assert await (await _service(session, FakePanel())).award_first_claim(invitee) is None


async def test_award_skips_missing_or_banned_inviter(session) -> None:
    orphan = await _add(session, telegram_id=2, referred_by=999)  # no such inviter
    assert await (await _service(session, FakePanel())).award_first_claim(orphan) is None

    await _add(session, telegram_id=3, status=UserStatus.banned)
    invitee = await _add(session, telegram_id=4, referred_by=3)
    assert await (await _service(session, FakePanel())).award_first_claim(invitee) is None
