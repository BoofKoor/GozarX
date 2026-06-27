"""Landing-flow wiring: menu:config (landing) provisions NOTHING; config:claim provisions.

DB-gated (real session + repos) + fakeredis + a ``FakePanel`` stub. The handlers edit via a guarded
``isinstance(.., Message)`` check, so with a stub ``message=None`` we assert the side effects (panel
calls + user state), which is exactly the spec's "creates no panel user" guarantee.
"""

from __future__ import annotations

import json
import os
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import fakeredis.aioredis
import pytest

from gozar.bot.handlers.config import open_config, start_claim
from gozar.cache.redis import SETTINGS_KEY
from gozar.db.models.enums import Language, UserStatus
from gozar.db.models.user import User
from gozar.db.repositories.config_log import ConfigLogRepository
from gozar.remnawave.schemas import PanelUser, Subscription, SubscriptionUser
from gozar.services.content import ContentService
from gozar.services.settings_service import SettingKey, SettingsService
from gozar.services.trial import TrialService

pytestmark = pytest.mark.skipif(
    not os.environ.get("TEST_DATABASE_URL"), reason="TEST_DATABASE_URL not set"
)

_SETTINGS = {
    SettingKey.TRIAL_SQUAD: "sq1",
    SettingKey.LOCATIONS: "",
    SettingKey.DAILY_LIMIT_MB: "1024",
    SettingKey.REFERRAL_REWARD_MB: "500",
    SettingKey.REFERRAL_REWARD_LIMIT: "10",
    SettingKey.TRIAL_HOURS: "24",
}
_CONTENT = {
    "cache:content:en:config_size": "allowance {size}",
    "cache:content:en:config_active": "active {remaining} {usage}/{total}",
    "cache:content:en:choose_location": "pick a location",
    "cache:content:en:panel_error": "panel error",
}


class FakePanel:
    def __init__(self, sub=None) -> None:
        self.created: list[str] = []
        self._sub = sub  # (Subscription, {name: link}) returned by subscription()

    async def create_trial_user(self, username, traffic_bytes, expire_at, squad_uuids) -> PanelUser:
        self.created.append(username)
        return PanelUser(uuid="u1", username=username)

    async def subscription(self, username: str):
        return self._sub


def _sub(*, status: str = "ACTIVE", expires_hours: float = 12) -> Subscription:
    expires = (datetime.now(UTC) + timedelta(hours=expires_hours)).isoformat()
    return Subscription(
        is_found=True,
        user=SubscriptionUser(
            user_status=status,
            expires_at=expires,
            traffic_used_bytes=0,
            traffic_limit_bytes=1024 * 1024 * 1024,
            short_uuid="su1",
        ),
    )


async def _setup(session, panel):
    redis = fakeredis.aioredis.FakeRedis(decode_responses=True)
    await redis.set(SETTINGS_KEY, json.dumps(_SETTINGS))
    for key, body in _CONTENT.items():
        await redis.set(key, body)
    settings = SettingsService(session, redis)
    trial = TrialService(panel, settings, ConfigLogRepository(session), redis)
    return trial, ContentService(session, redis)


def _callback():
    async def answer(*a, **k) -> None:
        return None

    return SimpleNamespace(answer=answer, message=None)


async def _user(session, **kw) -> User:
    user = User(language=Language.en, **kw)
    session.add(user)
    await session.flush()
    return user


async def test_menu_config_landing_creates_no_panel_user(session) -> None:
    panel = FakePanel()  # subscription unused for a claimable user
    trial, content = await _setup(session, panel)
    user = await _user(session, telegram_id=1, status=UserStatus.available)

    await open_config(_callback(), user, content, trial)

    assert panel.created == []  # the landing must NOT provision
    assert user.status is UserStatus.available


async def test_config_claim_provisions_and_flips_active(session) -> None:
    panel = FakePanel(sub=(_sub(), {"Germany": "vless://de#Germany"}))
    trial, content = await _setup(session, panel)
    user = await _user(session, telegram_id=2, status=UserStatus.available)

    await start_claim(_callback(), user, content, trial)

    assert panel.created  # config:claim is the only place that provisions
    assert user.status is UserStatus.active_config


async def test_menu_config_landing_self_heals_expired(session) -> None:
    panel = FakePanel(sub=(_sub(status="EXPIRED"), {"Germany": "vless://de#Germany"}))
    trial, content = await _setup(session, panel)
    user = await _user(
        session, telegram_id=3, status=UserStatus.active_config, panel_username="g3_old"
    )

    await open_config(_callback(), user, content, trial)

    assert panel.created == []  # landing never provisions, even while healing
    assert user.status is UserStatus.available  # expired trial self-healed to claimable
