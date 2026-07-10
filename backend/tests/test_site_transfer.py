"""P6 — device transfer: one-time code mint + single-use redeem that switches browser identity.

Service tests are DB-gated with fakeredis; endpoint tests drive the real ASGI app and assert that a
redeem on a FRESH client re-points its cookie to the source device (its /status then returns the
source's ref_code).
"""

from __future__ import annotations

import json

import fakeredis.aioredis
import httpx
import pytest_asyncio
from httpx import ASGITransport

from gozar.cache.redis import SETTINGS_KEY, site_transfer_key
from gozar.config.settings import get_settings
from gozar.db.models.site_device import SiteDevice, SiteDeviceStatus
from gozar.db.repositories.site_device import SiteDeviceRepository
from gozar.services.settings_service import SiteSettingKey
from gozar.services.site_transfer import _ALPHABET, _CODE_LEN, SiteTransferService
from gozar.web.app import create_app

_SETTINGS = {SiteSettingKey.SITE_TRIAL_SQUAD: "sq", SiteSettingKey.SITE_DAILY_LIMIT_MB: "1024"}


async def _redis() -> fakeredis.aioredis.FakeRedis:
    redis = fakeredis.aioredis.FakeRedis(decode_responses=True)
    await redis.set(SETTINGS_KEY, json.dumps(_SETTINGS))
    return redis


async def _device(session, **kw) -> SiteDevice:
    device = SiteDevice(uuid=kw.pop("uuid", "dev-src"), **kw)
    session.add(device)
    await session.flush()
    return device


def _service(session, redis) -> SiteTransferService:
    return SiteTransferService(SiteDeviceRepository(session), redis)


# --- service ------------------------------------------------------------------------------------


async def test_create_code_shape_and_ttl(session) -> None:
    redis = await _redis()
    device = await _device(session)
    result = await _service(session, redis).create_code(device)

    assert result is not None
    assert len(result.code) == _CODE_LEN
    assert set(result.code) <= set(_ALPHABET)  # only unambiguous uppercase chars
    assert result.expires_in == 600
    assert await redis.get(site_transfer_key(result.code)) == device.uuid
    assert 0 < await redis.ttl(site_transfer_key(result.code)) <= 600


async def test_redeem_is_single_use(session) -> None:
    redis = await _redis()
    svc = _service(session, redis)
    device = await _device(session, referral_count=4, status=SiteDeviceStatus.active_config)
    code = (await svc.create_code(device)).code

    first = await svc.redeem(code)
    assert first is not None
    assert first.device_uuid == device.uuid
    assert first.has_config is True
    assert first.referral_count == 4

    assert await svc.redeem(code) is None  # GETDEL consumed it


async def test_redeem_normalizes_case_spaces_and_display_hyphen(session) -> None:
    redis = await _redis()
    svc = _service(session, redis)
    device = await _device(session)
    code = (await svc.create_code(device)).code
    # The SPA shows the 8 chars as XXXX-XXXX (hyphen is display-only); pasted back with the hyphen,
    # lowercased and space-padded, it must still redeem.
    display = f"  {code[:4].lower()}-{code[4:].lower()}  "

    result = await svc.redeem(display)
    assert result is not None and result.device_uuid == device.uuid


async def test_redeem_unknown_code_returns_none(session) -> None:
    assert await _service(session, await _redis()).redeem("ZZZZZZZZ") is None


async def test_redeem_empty_code_returns_none(session) -> None:
    assert await _service(session, await _redis()).redeem("   ") is None


async def test_redeem_vanished_source_device_returns_none(session) -> None:
    redis = await _redis()
    # A code pointing at a device that no longer exists (deleted after minting).
    await redis.set(site_transfer_key("ABCD2345"), "ghost-uuid", ex=600)
    assert await _service(session, redis).redeem("ABCD2345") is None


async def test_create_code_returns_none_when_exhausted(session, monkeypatch) -> None:
    redis = await _redis()
    svc = _service(session, redis)
    device = await _device(session)
    # Force every mint attempt to collide with a pre-existing live code.
    monkeypatch.setattr(svc, "_new_code", lambda: "FIXED234")
    await redis.set(site_transfer_key("FIXED234"), "someone-else", ex=600)
    assert await svc.create_code(device) is None


# --- endpoints ----------------------------------------------------------------------------------


@pytest_asyncio.fixture
async def app(db_sessions):
    get_settings.cache_clear()
    application = create_app()
    application.state.sessionmaker = db_sessions
    application.state.redis = fakeredis.aioredis.FakeRedis(decode_responses=True)
    application.state.panel = None
    application.state.http = None
    await application.state.redis.set(SETTINGS_KEY, json.dumps(_SETTINGS))
    yield application
    get_settings.cache_clear()


def _client(application) -> httpx.AsyncClient:
    return httpx.AsyncClient(transport=ASGITransport(app=application), base_url="http://t")


async def test_endpoint_create_returns_code(app) -> None:
    async with _client(app) as client:
        resp = await client.post("/api/public/transfer/create")
        body = resp.json()
    assert resp.status_code == 200
    assert body["ok"] is True
    assert len(body["code"]) == _CODE_LEN and body["expires_in"] == 600


async def test_endpoint_redeem_switches_identity(app) -> None:
    async with _client(app) as source, _client(app) as fresh:
        src_uuid = (await source.get("/api/public/status")).json()["ref_code"]
        code = (await source.post("/api/public/transfer/create")).json()["code"]

        redeem = await fresh.post("/api/public/transfer/redeem", json={"code": code})
        assert redeem.json()["ok"] is True
        # The fresh browser now IS the source device — its status carries the source's ref_code.
        after = (await fresh.get("/api/public/status")).json()
    assert after["ref_code"] == src_uuid


async def test_endpoint_redeem_invalid_code(app) -> None:
    async with _client(app) as client:
        resp = await client.post("/api/public/transfer/redeem", json={"code": "ZZZZZZZZ"})
    body = resp.json()
    assert resp.status_code == 200 and body["ok"] is False and body["reason"] == "invalid"
