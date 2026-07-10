"""P2 — the public API spine: device-identity cookie, rate limit, Turnstile, and status/config.

Unit tests (cookie HMAC, rate limit, Turnstile) run without a DB; the endpoint tests are DB-gated
(the ``db_sessions`` fixture) and drive the real ASGI app with httpx + ASGITransport, like
``test_admin_api.py`` — no lifespan / real Redis.
"""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator

import fakeredis.aioredis
import httpx
import pytest_asyncio
from httpx import ASGITransport, MockTransport, Response
from sqlalchemy import func, select

from gozar.cache.redis import site_ratelimit_key
from gozar.config.settings import get_settings
from gozar.db.models.site_device import SiteDevice
from gozar.web.app import create_app
from gozar.web.routes.public.identity import (
    DEVICE_COOKIE,
    sign_device,
    verify_device_cookie,
)
from gozar.web.routes.public.security import rate_limit_ok, verify_turnstile

# --- cookie HMAC (pure) --------------------------------------------------------------------------


def test_sign_verify_roundtrip() -> None:
    u = str(uuid.uuid4())
    assert verify_device_cookie(sign_device(u, "secret"), "secret") == u


def test_verify_rejects_tampered_mac() -> None:
    signed = sign_device(str(uuid.uuid4()), "secret")
    tampered = signed[:-1] + ("0" if signed[-1] != "0" else "1")
    assert verify_device_cookie(tampered, "secret") is None


def test_verify_rejects_wrong_secret() -> None:
    signed = sign_device(str(uuid.uuid4()), "secret")
    assert verify_device_cookie(signed, "different-secret") is None


def test_verify_rejects_non_uuid_subject() -> None:
    # A correctly-signed but non-uuid subject must still be rejected.
    assert verify_device_cookie(sign_device("not-a-uuid", "secret"), "secret") is None


def test_verify_rejects_garbage() -> None:
    assert verify_device_cookie("", "secret") is None
    assert verify_device_cookie("no-dot-here", "secret") is None


# --- rate limit (fakeredis, pure) ----------------------------------------------------------------


async def test_rate_limit_allows_then_blocks() -> None:
    redis = fakeredis.aioredis.FakeRedis(decode_responses=True)
    for _ in range(3):
        assert await rate_limit_ok(redis, "claim", "dev1", limit=3, window_seconds=60) is True
    assert await rate_limit_ok(redis, "claim", "dev1", limit=3, window_seconds=60) is False


async def test_rate_limit_always_sets_ttl() -> None:
    redis = fakeredis.aioredis.FakeRedis(decode_responses=True)
    await rate_limit_ok(redis, "claim", "dev2", limit=5, window_seconds=42)
    ttl = await redis.ttl(site_ratelimit_key("claim", "dev2"))
    assert 0 < ttl <= 42  # a leaked (never-expiring) key would be -1


async def test_rate_limit_isolated_per_identifier() -> None:
    redis = fakeredis.aioredis.FakeRedis(decode_responses=True)
    assert await rate_limit_ok(redis, "claim", "A", limit=1, window_seconds=60) is True
    assert await rate_limit_ok(redis, "claim", "A", limit=1, window_seconds=60) is False
    assert await rate_limit_ok(redis, "claim", "B", limit=1, window_seconds=60) is True


# --- Turnstile (mocked httpx) --------------------------------------------------------------------


async def test_turnstile_skipped_when_unconfigured(monkeypatch) -> None:
    monkeypatch.delenv("TURNSTILE_SECRET", raising=False)
    get_settings.cache_clear()
    async with httpx.AsyncClient(transport=MockTransport(lambda r: Response(500))) as client:
        assert await verify_turnstile(client, "any-token", "1.2.3.4") is True
    get_settings.cache_clear()


async def test_turnstile_success_and_failure(monkeypatch) -> None:
    monkeypatch.setenv("TURNSTILE_SECRET", "sekret")
    get_settings.cache_clear()
    ok = httpx.AsyncClient(transport=MockTransport(lambda r: Response(200, json={"success": True})))
    no = httpx.AsyncClient(
        transport=MockTransport(lambda r: Response(200, json={"success": False}))
    )
    assert await verify_turnstile(ok, "tok", "1.2.3.4") is True
    assert await verify_turnstile(no, "tok", "1.2.3.4") is False
    assert await verify_turnstile(ok, "", "1.2.3.4") is False  # empty token never verifies
    await ok.aclose()
    await no.aclose()
    get_settings.cache_clear()


async def test_turnstile_transient_error_fails_closed(monkeypatch) -> None:
    monkeypatch.setenv("TURNSTILE_SECRET", "sekret")
    get_settings.cache_clear()

    def boom(_request):
        raise httpx.ConnectError("cloudflare down")

    async with httpx.AsyncClient(transport=MockTransport(boom)) as client:
        assert await verify_turnstile(client, "tok", "1.2.3.4") is False
    get_settings.cache_clear()


# --- endpoints (DB-gated) ------------------------------------------------------------------------


@pytest_asyncio.fixture
async def site_client(db_sessions) -> AsyncIterator[httpx.AsyncClient]:
    get_settings.cache_clear()
    app = create_app()
    app.state.sessionmaker = db_sessions
    app.state.redis = fakeredis.aioredis.FakeRedis(decode_responses=True)
    app.state.panel = None  # an available device never calls the panel; status stays device-level
    transport = ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://t") as client:
        yield client
    get_settings.cache_clear()


async def test_status_mints_device_and_sets_cookie(site_client: httpx.AsyncClient) -> None:
    resp = await site_client.get("/api/public/status")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "available"
    assert body["has_config"] is False
    assert body["referral_count"] == 0
    assert DEVICE_COOKIE in resp.cookies  # a signed device cookie was issued


async def test_returning_device_not_reminted(site_client: httpx.AsyncClient, db_sessions) -> None:
    first = await site_client.get("/api/public/status")
    assert first.status_code == 200
    second = await site_client.get("/api/public/status")
    assert second.status_code == 200
    # A valid returning cookie resolves the existing device — no new cookie is set.
    assert DEVICE_COOKIE not in second.cookies
    async with db_sessions() as session:
        count = await session.scalar(select(func.count()).select_from(SiteDevice))
    assert count == 1  # exactly one device across both requests


async def test_config_returns_public_keys_unconfigured(site_client: httpx.AsyncClient) -> None:
    resp = await site_client.get("/api/public/config")
    assert resp.status_code == 200
    body = resp.json()
    assert body["turnstile_enabled"] is False
    assert body["turnstile_site_key"] == ""
    assert body["vapid_public_key"] == ""
