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
from gozar.web.auth.jwt import TYPE_ACCESS, create_access, create_refresh, decode
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


async def test_login_unconfigured_503(client: httpx.AsyncClient, monkeypatch) -> None:
    monkeypatch.setenv("ADMIN_PASSWORD_HASH", "")
    get_settings.cache_clear()
    r = await client.post("/api/admin/auth/login", json={"username": "root", "password": "x"})
    assert r.status_code == 503
