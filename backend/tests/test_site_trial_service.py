"""SiteTrialService: provision, the status-flip-LAST ordering, by-NAME link matching, the rolling
cooldown, self-heal / change-location, and the site economy — plus /locations + /claim endpoints.

DB-gated (real session + repos) with fakeredis and a ``FakePanel`` stub for the Remnawave client.
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

from gozar.cache.redis import SETTINGS_KEY, site_sub_cache_key
from gozar.config.settings import get_settings
from gozar.db.models.site_claim import SiteClaim
from gozar.db.models.site_device import SiteDevice, SiteDeviceStatus
from gozar.db.repositories.site_claim import SiteClaimRepository
from gozar.remnawave.errors import RemnawaveError
from gozar.remnawave.schemas import PanelUser, Subscription, SubscriptionUser
from gozar.services.settings_service import SettingsService, SiteSettingKey
from gozar.services.site_trial import (
    AlreadyClaimedToday,
    Delivered,
    NoLocations,
    NotReady,
    PanelError,
    SiteTrialService,
)
from gozar.web.app import create_app

_BASE = {
    SiteSettingKey.SITE_TRIAL_SQUAD: "sq-site",
    SiteSettingKey.SITE_LOCATIONS: "",  # empty allowlist -> keep all
    SiteSettingKey.SITE_DAILY_LIMIT_MB: "1024",
    SiteSettingKey.SITE_REFERRAL_REWARD_MB: "500",
    SiteSettingKey.SITE_REFERRAL_REWARD_LIMIT: "10",
    SiteSettingKey.SITE_TRIAL_HOURS: "24",
}
_GB = 1024 * 1024 * 1024
_MB = 1024 * 1024


def _iso(hours: float) -> str:
    return (datetime.now(UTC) + timedelta(hours=hours)).isoformat()


def _sub(
    *, status: str = "ACTIVE", expires_hours: float = 12, used: int = 0, limit: int = 0
) -> Subscription:
    return Subscription(
        is_found=True,
        user=SubscriptionUser(
            user_status=status,
            expires_at=_iso(expires_hours),
            traffic_used_bytes=used,
            traffic_limit_bytes=limit,
        ),
    )


class FakePanel:
    def __init__(self, sub_queue, *, create_error: Exception | None = None) -> None:
        self.sub_queue = sub_queue
        self.create_error = create_error
        self.created: list[tuple] = []
        self.deleted: list[str] = []
        self._idx = 0

    async def create_trial_user(self, username, traffic_bytes, expire_at, squad_uuids):
        self.created.append((username, traffic_bytes, expire_at, squad_uuids))
        if self.create_error is not None:
            raise self.create_error
        return PanelUser(uuid="u1", username=username)

    async def subscription(self, username):
        item = self.sub_queue[self._idx]
        if self._idx < len(self.sub_queue) - 1:
            self._idx += 1
        if isinstance(item, Exception):
            raise item
        return item

    async def delete_user_by_username(self, username):
        self.deleted.append(username)
        return True


async def _service(session, panel, **overrides) -> SiteTrialService:
    redis = fakeredis.aioredis.FakeRedis(decode_responses=True)
    await redis.set(SETTINGS_KEY, json.dumps({**_BASE, **overrides}))
    return SiteTrialService(
        panel, SettingsService(session, redis), SiteClaimRepository(session), redis
    )


async def _device(session, **kw) -> SiteDevice:
    device = SiteDevice(uuid=kw.pop("uuid", "dev-1"), **kw)
    session.add(device)
    await session.flush()
    return device


_TWO = {"Germany": "vless://de#Germany", "Ukraine": "vless://ua#Ukraine"}


# --- service ------------------------------------------------------------------------------------


async def test_claim_provisions_and_delivers_by_name(session) -> None:
    panel = FakePanel([(_sub(), _TWO)])
    svc = await _service(session, panel)
    device = await _device(session)

    result = await svc.claim(device, "Ukraine")

    assert isinstance(result, Delivered)
    assert result.location == "Ukraine"
    assert result.link == "vless://ua#Ukraine"  # matched by NAME, not index
    assert result.changed is False
    assert device.status == SiteDeviceStatus.active_config
    assert device.site_panel_username.startswith("s")  # site prefix, not the bot's "g"
    assert device.last_claim_at is not None  # cooldown anchor set at provision
    assert panel.created[0][1] == _GB  # base allowance, no referrals
    assert panel.created[0][3] == ["sq-site"]
    # a site_claims row logged for the delivered location NAME
    n = await session.scalar(
        select(func.count()).select_from(SiteClaim).where(SiteClaim.location == "Ukraine")
    )
    assert n == 1


async def test_claim_create_failure_leaves_device_available(session) -> None:
    panel = FakePanel([(_sub(), _TWO)], create_error=RemnawaveError("boom"))
    svc = await _service(session, panel)
    device = await _device(session)

    result = await svc.claim(device, "Germany")

    assert isinstance(result, PanelError)
    assert device.status == SiteDeviceStatus.available  # flip is LAST — never half-committed
    assert device.site_panel_username is None


async def test_claim_empty_links_is_no_locations_no_flip(session) -> None:
    panel = FakePanel([(_sub(), {})])
    svc = await _service(session, panel)
    device = await _device(session)

    result = await svc.claim(device, "Germany")

    assert isinstance(result, NoLocations)
    assert device.status == SiteDeviceStatus.available


async def test_cooldown_blocks_second_claim(session) -> None:
    panel = FakePanel([(_sub(), _TWO)])
    svc = await _service(session, panel)
    device = await _device(session, last_claim_at=datetime.now(UTC) - timedelta(hours=1))

    result = await svc.claim(device, "Germany")

    assert isinstance(result, AlreadyClaimedToday)
    assert not panel.created  # never reached the panel


async def test_not_ready_without_squad(session) -> None:
    panel = FakePanel([(_sub(), _TWO)])
    svc = await _service(session, panel, **{SiteSettingKey.SITE_TRIAL_SQUAD: ""})
    device = await _device(session)

    assert isinstance(await svc.claim(device, "Germany"), NotReady)
    assert not panel.created


async def test_allowlist_filters_locations(session) -> None:
    panel = FakePanel([(_sub(), _TWO)])
    svc = await _service(session, panel, **{SiteSettingKey.SITE_LOCATIONS: "Germany"})
    device = await _device(session)

    result = await svc.claim(device, "Ukraine")  # Ukraine filtered out -> only Germany remains
    assert isinstance(result, Delivered)
    assert result.location == "Germany"  # falls back to the only allowed location


async def test_referral_bonus_in_provisioned_traffic(session) -> None:
    panel = FakePanel([(_sub(), _TWO)])
    svc = await _service(session, panel)
    device = await _device(session, referral_count=3)

    await svc.claim(device, "Germany")
    assert panel.created[0][1] == (1024 + 3 * 500) * 1024 * 1024  # base + capped referral bonus


async def test_already_active_is_change_location_no_reprovision(session) -> None:
    panel = FakePanel([(_sub(), _TWO)])  # the refresh read
    svc = await _service(session, panel)
    device = await _device(
        session, status=SiteDeviceStatus.active_config, site_panel_username="s-existing"
    )

    result = await svc.claim(device, "Ukraine")

    assert isinstance(result, Delivered)
    assert result.changed is True
    assert result.link == "vless://ua#Ukraine"
    assert not panel.created  # reused the live account — no new provision


async def test_active_expired_self_heals_then_reclaims(session) -> None:
    # First subscription read (refresh) shows EXPIRED -> reset; then a fresh claim provisions.
    panel = FakePanel([(_sub(status="EXPIRED"), {}), (_sub(), _TWO)])
    svc = await _service(session, panel)
    device = await _device(
        session, status=SiteDeviceStatus.active_config, site_panel_username="s-dead"
    )

    result = await svc.claim(device, "Germany")

    assert isinstance(result, Delivered)  # self-healed and re-provisioned
    assert "s-dead" in panel.deleted  # the dead account was cleaned up
    assert len(panel.created) == 1


async def test_available_locations_fresh_uses_setting(session) -> None:
    panel = FakePanel([])
    svc = await _service(session, panel, **{SiteSettingKey.SITE_LOCATIONS: "Germany,Ukraine"})
    device = await _device(session)
    assert await svc.available_locations(device) == ["Germany", "Ukraine"]


async def test_available_locations_active_uses_cache(session) -> None:
    panel = FakePanel([])
    svc = await _service(session, panel)
    device = await _device(session, status=SiteDeviceStatus.active_config)
    # prime the device subscription cache
    await svc._redis.set(
        site_sub_cache_key(device.uuid), json.dumps({"links": _TWO, "expires": _iso(5)})
    )
    assert set(await svc.available_locations(device)) == {"Germany", "Ukraine"}


# --- status (P4) --------------------------------------------------------------------------------


async def test_status_available_fresh_device(session) -> None:
    svc = await _service(session, FakePanel([]))
    device = await _device(session)
    info = await svc.status(device)
    assert info.active is False
    assert info.has_config is False
    assert info.live is True
    assert info.can_claim is True
    assert info.configs == 0
    assert info.daily_limit_bytes == _GB  # base allowance


async def test_status_active_reports_live_traffic_and_location(session) -> None:
    panel = FakePanel([(_sub(used=200 * _MB, limit=_GB), _TWO)])
    svc = await _service(session, panel)
    device = await _device(
        session, status=SiteDeviceStatus.active_config, site_panel_username="s-live"
    )
    await SiteClaimRepository(session).add(device.uuid, "Germany")  # current config location

    info = await svc.status(device)

    assert info.active is True and info.has_config is True and info.live is True
    assert info.usage_bytes == 200 * _MB
    assert info.remaining != "—"
    assert info.location == "Germany"
    assert info.link == "vless://de#Germany"
    assert info.configs == 1


async def test_status_cooldown_blocks_next_claim(session) -> None:
    svc = await _service(session, FakePanel([]))
    device = await _device(session, last_claim_at=datetime.now(UTC) - timedelta(hours=2))
    info = await svc.status(device)
    assert info.can_claim is False
    assert info.cooldown  # a non-empty "time until next claim"


async def test_status_panel_down_degrades_not_errors(session) -> None:
    panel = FakePanel([RemnawaveError("down")])  # subscription raises a transient error
    svc = await _service(session, panel)
    device = await _device(
        session, status=SiteDeviceStatus.active_config, site_panel_username="s-x"
    )
    info = await svc.status(device)
    assert info.live is False  # panel unreachable
    assert info.active is True  # device still considered active (state untouched)
    assert info.usage == "—"


async def test_status_data_exhausted_stays_active(session) -> None:
    panel = FakePanel([(_sub(status="LIMITED"), _TWO)])
    svc = await _service(session, panel)
    device = await _device(
        session, status=SiteDeviceStatus.active_config, site_panel_username="s-lim"
    )
    info = await svc.status(device)
    assert info.data_exhausted is True
    assert info.active is True  # LIMITED but time valid -> revivable, stays active


async def test_status_active_expired_self_heals(session) -> None:
    panel = FakePanel([(_sub(status="EXPIRED"), {})])
    svc = await _service(session, panel)
    device = await _device(
        session, status=SiteDeviceStatus.active_config, site_panel_username="s-dead"
    )
    info = await svc.status(device)
    assert info.active is False  # self-healed to available
    assert device.status == SiteDeviceStatus.available
    assert "s-dead" in panel.deleted


# --- endpoints ----------------------------------------------------------------------------------


class _StubPanel:
    def __init__(self) -> None:
        self.created: list[tuple] = []

    async def create_trial_user(self, username, traffic_bytes, expire_at, squad_uuids):
        self.created.append((username, traffic_bytes, expire_at, squad_uuids))
        return PanelUser(uuid="u1", username=username)

    async def subscription(self, username):
        return _sub(), {"Germany": "vless://de#Germany"}


@pytest_asyncio.fixture
async def claim_env(db_sessions) -> AsyncIterator[tuple[httpx.AsyncClient, object]]:
    get_settings.cache_clear()
    app = create_app()
    app.state.sessionmaker = db_sessions
    app.state.redis = fakeredis.aioredis.FakeRedis(decode_responses=True)
    app.state.panel = _StubPanel()
    app.state.http = None  # Turnstile unconfigured -> skipped, never touches the client
    await app.state.redis.set(SETTINGS_KEY, json.dumps(_BASE))
    transport = ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://t") as client:
        yield client, app
    get_settings.cache_clear()


async def test_endpoint_claim_then_status(claim_env) -> None:
    client, _app = claim_env
    resp = await client.post("/api/public/claim", json={"location": "Germany"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["ok"] is True
    assert body["location"] == "Germany"
    assert body["link"] == "vless://de#Germany"
    status = await client.get("/api/public/status")
    body = status.json()
    assert body["has_config"] is True
    assert body["active"] is True
    assert body["location"] == "Germany"
    assert body["link"] == "vless://de#Germany"
    assert body["configs"] == 1


async def test_endpoint_locations(claim_env) -> None:
    client, app = claim_env
    await app.state.redis.set(
        SETTINGS_KEY, json.dumps({**_BASE, SiteSettingKey.SITE_LOCATIONS: "Germany,Ukraine"})
    )
    resp = await client.get("/api/public/locations")
    assert resp.status_code == 200
    assert resp.json()["locations"] == ["Germany", "Ukraine"]


async def test_endpoint_second_claim_is_change_location(claim_env) -> None:
    client, app = claim_env
    first = await client.post("/api/public/claim", json={"location": "Germany"})
    assert first.json()["ok"] is True
    second = await client.post("/api/public/claim", json={"location": "Germany"})
    body = second.json()
    assert body["ok"] is True
    assert body["changed"] is True  # active device -> change-location, not a new provision
    assert len(app.state.panel.created) == 1  # provisioned exactly once
