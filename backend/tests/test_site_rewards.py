"""P5 — site rewards (one-time PWA/notifications + daily streak) and the referral economy.

Service tests are DB-gated with fakeredis + tiny panel stubs; endpoint tests drive the real app.
"""

from __future__ import annotations

import json
from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta

import fakeredis.aioredis
import httpx
import pytest_asyncio
from httpx import ASGITransport
from sqlalchemy import func, select

from gozar.cache.redis import SETTINGS_KEY
from gozar.config.settings import get_settings
from gozar.db.models.push_subscription import PushSubscription
from gozar.db.models.site_device import SiteDevice, SiteDeviceStatus
from gozar.db.models.site_reward import SiteReward, SiteRewardType
from gozar.db.repositories.push_subscription import PushSubscriptionRepository
from gozar.db.repositories.site_device import SiteDeviceRepository
from gozar.db.repositories.site_reward import SiteRewardRepository
from gozar.remnawave.schemas import PanelUser
from gozar.services.settings_service import SettingsService, SiteSettingKey
from gozar.services.site_economy import site_device_allowance_bytes
from gozar.services.site_referral import SiteReferralService
from gozar.services.site_reward import SiteRewardService
from gozar.web.app import create_app

_MB = 1024 * 1024
_SETTINGS = {
    SiteSettingKey.SITE_DAILY_LIMIT_MB: "1024",
    SiteSettingKey.SITE_REFERRAL_REWARD_MB: "500",
    SiteSettingKey.SITE_REFERRAL_REWARD_LIMIT: "10",
    SiteSettingKey.SITE_REWARD_PWA_MB: "200",
    SiteSettingKey.SITE_REWARD_PUSH_MB: "150",
    SiteSettingKey.SITE_REWARD_STREAK_MB: "300",
    SiteSettingKey.SITE_STREAK_DAYS: "7",
    SiteSettingKey.SITE_TRIAL_HOURS: "24",
}


class BumpPanel:
    """Stub for the live-trial bump: exposes get_user + update_traffic_limit and records bumps."""

    def __init__(self, user: PanelUser | None = None) -> None:
        self._user = user
        self.bumped: list[tuple[str, int]] = []

    async def get_user(self, username):
        return self._user

    async def update_traffic_limit(self, uuid, traffic_bytes):
        self.bumped.append((uuid, traffic_bytes))
        return PanelUser(uuid=uuid)


async def _redis(**overrides):
    redis = fakeredis.aioredis.FakeRedis(decode_responses=True)
    await redis.set(SETTINGS_KEY, json.dumps({**_SETTINGS, **overrides}))
    return redis


async def _device(session, **kw) -> SiteDevice:
    device = SiteDevice(uuid=kw.pop("uuid", "dev-1"), **kw)
    session.add(device)
    await session.flush()
    return device


def _reward_service(session, panel, redis) -> SiteRewardService:
    return SiteRewardService(
        SiteRewardRepository(session),
        SettingsService(session, redis),
        panel,
        redis,
        PushSubscriptionRepository(session),
    )


async def _subscribe(session, device_uuid: str, endpoint: str = "https://push/1") -> None:
    """Give a device an active push subscription (the push reward now requires one)."""
    session.add(
        PushSubscription(
            device_uuid=device_uuid, endpoint=endpoint, p256dh="p", auth="a", locale="fa"
        )
    )
    await session.flush()


# --- one-time rewards ---------------------------------------------------------------------------


async def test_pwa_reward_grants_once_and_bumps_live(session) -> None:
    redis = await _redis()
    panel = BumpPanel(PanelUser(uuid="u1", username="s-x"))
    device = await _device(
        session, status=SiteDeviceStatus.active_config, site_panel_username="s-x"
    )
    svc = _reward_service(session, panel, redis)

    first = await svc.claim(device, SiteRewardType.pwa)
    assert first.ok is True
    assert first.amount_mb == 200
    assert panel.bumped and panel.bumped[0][1] == (1024 + 200) * _MB  # live trial raised

    second = await svc.claim(device, SiteRewardType.pwa)
    assert second.ok is False and second.reason == "already_claimed"


async def test_push_reward_requires_active_subscription(session) -> None:
    """The push bonus is earned by actually enabling notifications — refused without a real
    subscription (closes the 'grant on the client's word' gap)."""
    svc = _reward_service(session, BumpPanel(), await _redis())
    device = await _device(session)  # no push subscription yet

    result = await svc.claim(device, SiteRewardType.push)
    assert result.ok is False and result.reason == "not_subscribed"


async def test_push_reward_with_subscription_no_bump(session) -> None:
    redis = await _redis()
    panel = BumpPanel()
    device = await _device(session)  # available — holds no live trial
    await _subscribe(session, device.uuid)  # opted in to notifications
    svc = _reward_service(session, panel, redis)

    result = await svc.claim(device, SiteRewardType.push)
    assert result.ok is True and result.amount_mb == 150
    assert panel.bumped == []  # nothing to bump


async def test_unknown_reward_type(session) -> None:
    svc = _reward_service(session, BumpPanel(), await _redis())
    result = await svc.claim(await _device(session), "mystery")
    assert result.ok is False and result.reason == "unknown_reward"


async def test_streak_is_not_a_claimable_reward(session) -> None:
    """The streak advances from consecutive config CLAIMS (SiteTrialService), never from the reward
    endpoint — so a 'streak' reward_type is now rejected like any unknown type."""
    svc = _reward_service(session, BumpPanel(), await _redis())
    result = await svc.claim(await _device(session), "streak")
    assert result.ok is False and result.reason == "unknown_reward"


# --- full allowance math ------------------------------------------------------------------------


async def test_full_allowance_includes_rewards_and_streak(session) -> None:
    redis = await _redis()
    settings = SettingsService(session, redis)
    device = await _device(session, referral_count=2, streak_count=7)
    session.add(SiteReward(device_uuid=device.uuid, reward_type=SiteRewardType.pwa, amount_mb=200))
    session.add(SiteReward(device_uuid=device.uuid, reward_type=SiteRewardType.push, amount_mb=150))
    await session.flush()

    total = await site_device_allowance_bytes(settings, device, SiteRewardRepository(session))
    # base + 2*referral + pwa + push + streak
    assert total == (1024 + 2 * 500 + 200 + 150 + 300) * _MB


# --- referral -----------------------------------------------------------------------------------


def _referral_service(session, panel, redis) -> SiteReferralService:
    return SiteReferralService(
        SiteDeviceRepository(session),
        SiteRewardRepository(session),
        SettingsService(session, redis),
        panel,
        redis,
    )


async def test_referral_credits_inviter(session) -> None:
    redis = await _redis()
    inviter = await _device(session, uuid="inviter", referral_count=0)
    invitee = await _device(session, uuid="invitee", referred_by="inviter")

    result = await _referral_service(session, BumpPanel(), redis).award_first_claim(invitee)

    assert result is not None
    assert result.new_count == 1
    assert inviter.referral_count == 1
    assert result.new_daily_bytes == (1024 + 500) * _MB  # inviter's recomputed allowance


async def test_referral_none_when_no_referrer(session) -> None:
    invitee = await _device(session, uuid="invitee")  # referred_by is None
    assert (
        await _referral_service(session, BumpPanel(), await _redis()).award_first_claim(invitee)
        is None
    )


async def test_referral_ignores_self_and_missing(session) -> None:
    redis = await _redis()
    self_ref = await _device(session, uuid="selfie", referred_by="selfie")
    assert await _referral_service(session, BumpPanel(), redis).award_first_claim(self_ref) is None
    missing = await _device(session, uuid="lonely", referred_by="ghost-uuid")
    assert await _referral_service(session, BumpPanel(), redis).award_first_claim(missing) is None


# --- endpoints ----------------------------------------------------------------------------------


class _ClaimPanel:
    async def create_trial_user(self, username, traffic_bytes, expire_at, squad_uuids):
        return PanelUser(uuid="u1", username=username)

    async def squad_location_names(self, squad_uuid):
        # The squad serves what this stub's subscription returns — scoping is a no-op here.
        return ["Germany"]

    async def subscription(self, username):
        from gozar.remnawave.schemas import Subscription, SubscriptionUser

        expires = (datetime.now(UTC) + timedelta(hours=12)).isoformat()
        return Subscription(
            is_found=True, user=SubscriptionUser(user_status="ACTIVE", expires_at=expires)
        ), {"Germany": "vless://de#Germany"}

    async def get_user(self, username):
        return None  # inviter is available in the test -> no bump


@pytest_asyncio.fixture
async def env(db_sessions) -> AsyncIterator[tuple[httpx.AsyncClient, object]]:
    get_settings.cache_clear()
    app = create_app()
    app.state.sessionmaker = db_sessions
    app.state.redis = fakeredis.aioredis.FakeRedis(decode_responses=True)
    app.state.panel = _ClaimPanel()
    app.state.http = None
    await app.state.redis.set(
        SETTINGS_KEY, json.dumps({**_SETTINGS, SiteSettingKey.SITE_TRIAL_SQUAD: "sq"})
    )
    transport = ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://t") as client:
        yield client, app
    get_settings.cache_clear()


async def test_endpoint_pwa_reward_once(env) -> None:
    client, _app = env
    first = await client.post("/api/public/rewards/claim", json={"reward_type": "pwa"})
    assert first.status_code == 200 and first.json()["ok"] is True
    second = await client.post("/api/public/rewards/claim", json={"reward_type": "pwa"})
    assert second.json()["ok"] is False and second.json()["reason"] == "already_claimed"


async def test_endpoint_streak_type_rejected(env) -> None:
    client, _app = env
    resp = await client.post("/api/public/rewards/claim", json={"reward_type": "streak"})
    body = resp.json()
    assert body["ok"] is False and body["reason"] == "unknown_reward"


async def test_endpoint_referral_flow_credits_inviter(env, db_sessions) -> None:
    client, _app = env
    inviter_uuid = "11111111-1111-1111-1111-111111111111"
    async with db_sessions() as s:
        s.add(SiteDevice(uuid=inviter_uuid))
        await s.commit()
    # invitee mints via the ref link, then claims -> the inviter is credited
    await client.get(f"/api/public/status?ref={inviter_uuid}")
    claim = await client.post("/api/public/claim", json={"location": "Germany"})
    assert claim.json()["ok"] is True
    async with db_sessions() as s:
        count = await s.scalar(
            select(func.count())
            .select_from(SiteDevice)
            .where(SiteDevice.referred_by == inviter_uuid)
        )
        inviter = await s.get(SiteDevice, inviter_uuid)
    assert count == 1  # invitee carries the referrer
    assert inviter.referral_count == 1  # credited on the invitee's first claim


async def test_endpoint_referral_by_handle_credits_inviter(env, db_sessions) -> None:
    """The invite link now uses the inviter's public HANDLE (?ref=GZ-…). The invitee minting via
    that link must resolve the handle to the inviter and credit them on the first claim."""
    client, _app = env
    async with db_sessions() as s:
        inviter = await SiteDeviceRepository(s).create("33333333-3333-3333-3333-333333333333")
        handle = inviter.handle
        await s.commit()
    await client.get(f"/api/public/status?ref={handle}")  # invitee mints via the handle link
    claim = await client.post("/api/public/claim", json={"location": "Germany"})
    assert claim.json()["ok"] is True
    async with db_sessions() as s:
        credited = await s.scalar(select(SiteDevice).where(SiteDevice.handle == handle))
    assert credited.referral_count == 1  # inviter credited via the handle ref
