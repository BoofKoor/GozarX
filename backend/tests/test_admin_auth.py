"""Admin auth — JWT round-trip/rejection + bcrypt verify (unit) and the login/refresh/me HTTP flow.

No DB needed: login/refresh/me only read env credentials + sign/verify JWTs. The HTTP layer is
driven with httpx + ASGITransport (same event loop, no lifespan) against the real auth routes.
"""

from __future__ import annotations

import time
from collections.abc import AsyncIterator, Iterator

import httpx
import jwt as pyjwt
import pytest
import pytest_asyncio
from httpx import ASGITransport

from gozar.config.settings import get_settings
from gozar.web.app import create_app
from gozar.web.auth import TokenInvalid
from gozar.web.auth.jwt import (
    SESSION_MAX,
    TYPE_ACCESS,
    TYPE_REFRESH,
    create_access,
    create_refresh,
    decode,
)
from gozar.web.auth.passwords import hash_password, verify_password

# ≥32 bytes so PyJWT doesn't warn about a weak HMAC key.
_SECRET = "test-admin-secret-0123456789-abcdef-ghijkl"
_PASSWORD = "s3cret-pw"


@pytest.fixture(autouse=True)
def _admin_env(monkeypatch) -> Iterator[None]:
    monkeypatch.setenv("ADMIN_JWT_SECRET", _SECRET)
    monkeypatch.setenv("ADMIN_USERNAME", "root")
    monkeypatch.setenv("ADMIN_PASSWORD_HASH", hash_password(_PASSWORD))
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


# ── unit: passwords ────────────────────────────────────────────────────────
def test_password_verify_true_false() -> None:
    h = hash_password("hunter2")
    assert verify_password("hunter2", h) is True
    assert verify_password("nope", h) is False


# ── unit: jwt ──────────────────────────────────────────────────────────────
def test_jwt_roundtrip() -> None:
    payload = decode(create_access("root"), TYPE_ACCESS)
    assert payload.sub == "root"
    assert payload.type == TYPE_ACCESS


def test_jwt_refresh_used_as_access_rejected() -> None:
    with pytest.raises(TokenInvalid):
        decode(create_refresh("root"), TYPE_ACCESS)


def test_jwt_bad_signature_rejected() -> None:
    with pytest.raises(TokenInvalid):
        decode(create_access("root") + "tamper", TYPE_ACCESS)


def test_jwt_expired_rejected() -> None:
    now = int(time.time())
    token = pyjwt.encode(
        {"sub": "root", "typ": "access", "aud": "gozar-admin", "iat": now - 100, "exp": now - 10},
        _SECRET,
        algorithm="HS256",
    )
    with pytest.raises(TokenInvalid):
        decode(token, TYPE_ACCESS)


def test_jwt_wrong_audience_rejected() -> None:
    now = int(time.time())
    token = pyjwt.encode(
        {"sub": "root", "typ": "access", "aud": "someone-else", "iat": now, "exp": now + 100},
        _SECRET,
        algorithm="HS256",
    )
    with pytest.raises(TokenInvalid):
        decode(token, TYPE_ACCESS)


def test_a_password_change_ends_every_existing_session(monkeypatch) -> None:
    """Tokens carry a fingerprint of the credentials they were minted under. A new password hash
    (and the restart that loads it) must cut off old sessions — a leaked one included — instead of
    leaving them working for another week, renewable forever."""
    access, refresh = create_access("root"), create_refresh("root")
    assert decode(access, TYPE_ACCESS).sub == "root"
    monkeypatch.setenv("ADMIN_PASSWORD_HASH", hash_password("a-new-password"))
    get_settings.cache_clear()
    with pytest.raises(TokenInvalid):
        decode(access, TYPE_ACCESS)
    with pytest.raises(TokenInvalid):
        decode(refresh, TYPE_REFRESH)


def test_a_token_from_before_sessions_were_versioned_is_rejected() -> None:
    now = int(time.time())
    legacy = pyjwt.encode(
        {"sub": "root", "typ": "access", "aud": "gozar-admin", "iat": now, "exp": now + 100},
        _SECRET,
        algorithm="HS256",
    )
    with pytest.raises(TokenInvalid):
        decode(legacy, TYPE_ACCESS)


def test_refreshing_keeps_the_login_time_and_cannot_outlive_the_session() -> None:
    """Each refresh re-minted a fresh seven days, so one stolen refresh token was a session that
    never ended. The login's own time rides every refresh, and nothing outlives SESSION_MAX."""
    started = int(time.time()) - SESSION_MAX + 60  # a login a minute short of its limit
    refresh = create_refresh("root", auth_time=started)
    payload = decode(refresh, TYPE_REFRESH)
    assert payload.auth_time == started
    assert payload.expires_at <= started + SESSION_MAX  # not now + 7 days
    # Past the limit, even a correctly signed refresh token is refused.
    too_old = create_refresh("root", auth_time=int(time.time()) - SESSION_MAX - 5)
    with pytest.raises(TokenInvalid):
        decode(too_old, TYPE_REFRESH)


# ── HTTP: login / refresh / me ─────────────────────────────────────────────
@pytest_asyncio.fixture
async def client() -> AsyncIterator[httpx.AsyncClient]:
    app = create_app()
    transport = ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://t") as c:
        yield c


async def test_login_success_then_me(client: httpx.AsyncClient) -> None:
    r = await client.post("/api/admin/auth/login", json={"username": "root", "password": _PASSWORD})
    assert r.status_code == 200
    token = r.json()["access_token"]
    me = await client.get("/api/admin/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert me.status_code == 200
    assert me.json()["username"] == "root"


async def test_login_bad_password_401(client: httpx.AsyncClient) -> None:
    r = await client.post("/api/admin/auth/login", json={"username": "root", "password": "wrong"})
    assert r.status_code == 401


async def test_me_requires_token(client: httpx.AsyncClient) -> None:
    assert (await client.get("/api/admin/auth/me")).status_code == 401


async def test_refresh_mints_new_access(client: httpx.AsyncClient) -> None:
    login = await client.post(
        "/api/admin/auth/login", json={"username": "root", "password": _PASSWORD}
    )
    refresh = login.json()["refresh_token"]
    r = await client.post("/api/admin/auth/refresh", json={"refresh_token": refresh})
    assert r.status_code == 200
    assert decode(r.json()["access_token"], TYPE_ACCESS).sub == "root"
    # The rotated pair continues the SAME login rather than starting a new one.
    started = decode(refresh, TYPE_REFRESH).auth_time
    assert decode(r.json()["refresh_token"], TYPE_REFRESH).auth_time == started


async def test_login_unconfigured_503(client: httpx.AsyncClient, monkeypatch) -> None:
    monkeypatch.setenv("ADMIN_PASSWORD_HASH", "")
    get_settings.cache_clear()
    r = await client.post("/api/admin/auth/login", json={"username": "root", "password": "x"})
    assert r.status_code == 503


async def test_login_attempts_are_rate_limited_per_ip() -> None:
    import fakeredis.aioredis

    app = create_app()
    app.state.redis = fakeredis.aioredis.FakeRedis(decode_responses=True)
    async with httpx.AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
        codes = [
            (
                await c.post("/api/admin/auth/login", json={"username": "root", "password": "x"})
            ).status_code
            for _ in range(11)
        ]
        # The limit counts attempts, not failures: even the right password waits out the window.
        right = await c.post(
            "/api/admin/auth/login", json={"username": "root", "password": _PASSWORD}
        )
    assert codes[:10] == [401] * 10
    assert codes[10] == 429 and right.status_code == 429
