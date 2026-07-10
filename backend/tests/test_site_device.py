"""P6 — device reset: the irreversible danger-row wipe (POST /device/reset + SiteDeviceService).

Service tests assert the row + its claims/rewards cascade away and the panel trial is freed
best-effort; the endpoint test asserts the identity cookie is cleared so the browser starts fresh.
"""

from __future__ import annotations

import json
from collections.abc import AsyncIterator

import fakeredis.aioredis
import httpx
import pytest_asyncio
from httpx import ASGITransport
from sqlalchemy import func, select

from gozar.cache.redis import SETTINGS_KEY, site_sub_cache_key
from gozar.config.settings import get_settings
from gozar.db.models.site_claim import SiteClaim
from gozar.db.models.site_device import SiteDevice, SiteDeviceStatus
from gozar.db.models.site_reward import SiteReward, SiteRewardType
from gozar.db.repositories.site_device import SiteDeviceRepository
from gozar.remnawave.errors import RemnawaveError
from gozar.services.site_device import SiteDeviceService
from gozar.web.app import create_app

_SETTINGS = {"site_daily_limit_mb": "1024"}


class _Panel:
    def __init__(self, *, fail: bool = False) -> None:
        self.deleted: list[str] = []
        self._fail = fail

    async def delete_user_by_username(self, username: str) -> bool:
        if self._fail:
            raise RemnawaveError("panel down", status_code=502)
        self.deleted.append(username)
        return True


async def _redis() -> fakeredis.aioredis.FakeRedis:
    return fakeredis.aioredis.FakeRedis(decode_responses=True)


async def _device_with_children(session, **kw) -> SiteDevice:
    device = SiteDevice(uuid=kw.pop("uuid", "dev-1"), **kw)
    session.add(device)
    await session.flush()
    session.add(SiteClaim(device_uuid=device.uuid, location="Germany"))
    session.add(SiteReward(device_uuid=device.uuid, reward_type=SiteRewardType.pwa, amount_mb=200))
    await session.flush()
    return device


async def _counts(session, uuid: str) -> tuple[int, int, int]:
    dev = await session.scalar(
        select(func.count()).select_from(SiteDevice).where(SiteDevice.uuid == uuid)
    )
    claims = await session.scalar(
        select(func.count()).select_from(SiteClaim).where(SiteClaim.device_uuid == uuid)
    )
    rewards = await session.scalar(
        select(func.count()).select_from(SiteReward).where(SiteReward.device_uuid == uuid)
    )
    return dev, claims, rewards


# --- service ------------------------------------------------------------------------------------


async def test_reset_deletes_device_and_cascades(session) -> None:
    redis = await _redis()
    panel = _Panel()
    device = await _device_with_children(
        session, status=SiteDeviceStatus.active_config, site_panel_username="s-x"
    )
    await redis.set(site_sub_cache_key(device.uuid), "cached")

    await SiteDeviceService(SiteDeviceRepository(session), panel, redis).reset(device)

    assert await _counts(session, "dev-1") == (0, 0, 0)  # row + claims + rewards gone
    assert panel.deleted == ["s-x"]  # live trial freed
    assert await redis.get(site_sub_cache_key("dev-1")) is None  # cache dropped


async def test_reset_available_device_skips_panel(session) -> None:
    panel = _Panel()
    device = await _device_with_children(session)  # available — no panel username
    await SiteDeviceService(SiteDeviceRepository(session), panel, await _redis()).reset(device)
    assert panel.deleted == []
    assert await _counts(session, "dev-1") == (0, 0, 0)


async def test_reset_survives_panel_failure(session) -> None:
    panel = _Panel(fail=True)
    device = await _device_with_children(
        session, status=SiteDeviceStatus.active_config, site_panel_username="s-x"
    )
    # Panel raises, but the local wipe still completes (best-effort).
    await SiteDeviceService(SiteDeviceRepository(session), panel, await _redis()).reset(device)
    assert await _counts(session, "dev-1") == (0, 0, 0)


# --- endpoint -----------------------------------------------------------------------------------


@pytest_asyncio.fixture
async def env(db_sessions) -> AsyncIterator[tuple[httpx.AsyncClient, object]]:
    get_settings.cache_clear()
    app = create_app()
    app.state.sessionmaker = db_sessions
    app.state.redis = fakeredis.aioredis.FakeRedis(decode_responses=True)
    app.state.panel = _Panel()
    app.state.http = None
    await app.state.redis.set(SETTINGS_KEY, json.dumps(_SETTINGS))
    transport = ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://t") as client:
        yield client, app
    get_settings.cache_clear()


async def test_endpoint_reset_clears_identity(env, db_sessions) -> None:
    client, _app = env
    first = (await client.get("/api/public/status")).json()["ref_code"]

    resp = await client.post("/api/public/device/reset")
    assert resp.status_code == 200 and resp.json()["ok"] is True

    # The old device row is gone...
    async with db_sessions() as s:
        gone = await s.get(SiteDevice, first)
    assert gone is None
    # ...and the browser now mints a brand-new identity (cookie was cleared).
    second = (await client.get("/api/public/status")).json()["ref_code"]
    assert second != first


async def test_endpoint_reset_cookieless_does_not_clear(env) -> None:
    client, _app = env
    client.cookies.clear()
    # A cookieless (e.g. cross-site CSRF) reset must NOT emit a cookie-clearing Set-Cookie — that
    # would delete a victim's identity cookie. It still returns ok (it has nothing of its own).
    resp = await client.post("/api/public/device/reset")
    assert resp.status_code == 200 and resp.json()["ok"] is True
    assert not resp.headers.get_list("set-cookie")
