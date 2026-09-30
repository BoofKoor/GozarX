"""Admin auth endpoints: login, refresh, me.

Single admin from env (``admin_username`` + bcrypt ``admin_password_hash`` + ``admin_jwt_secret``).
503 when the panel isn't configured yet; 401 on a credential/token mismatch.
"""

from __future__ import annotations

import asyncio
import hmac

from fastapi import APIRouter, HTTPException, Request, status
from pydantic import BaseModel

from gozar.config.settings import get_settings
from gozar.web.auth import AdminNotConfigured, TokenInvalid
from gozar.web.auth.jwt import TYPE_REFRESH, create_access, create_refresh, decode
from gozar.web.auth.passwords import verify_password
from gozar.web.dependencies import AdminUser
from gozar.web.routes.public.identity import client_ip
from gozar.web.routes.public.security import rate_limit_ok

router = APIRouter(prefix="/auth", tags=["auth"])

_NOT_CONFIGURED = "admin panel not configured"
#: Login attempts allowed per client IP per window. Generous for a person who mistypes, useless for
#: guessing: bcrypt already costs ~0.3s an attempt, and this caps it at ten a quarter hour.
_LOGIN_LIMIT = 10
_LOGIN_WINDOW = 15 * 60


class LoginIn(BaseModel):
    username: str
    password: str


class TokenOut(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class RefreshIn(BaseModel):
    refresh_token: str


def _require_configured() -> None:
    settings = get_settings()
    if not settings.admin_password_hash or not settings.admin_jwt_secret.get_secret_value():
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, _NOT_CONFIGURED)


async def _login_allowed(request: Request) -> bool:
    """Per-IP attempt limit. Fails OPEN when Redis is unavailable: the limiter is a brake on
    guessing, and a Redis outage must not also lock the operator out of the console."""
    redis = getattr(request.app.state, "redis", None)
    if redis is None:
        return True
    try:
        return await rate_limit_ok(
            redis,
            "admin_login",
            client_ip(request),
            limit=_LOGIN_LIMIT,
            window_seconds=_LOGIN_WINDOW,
        )
    except Exception:  # noqa: BLE001
        return True


@router.post("/login", response_model=TokenOut)
async def login(body: LoginIn, request: Request) -> TokenOut:
    _require_configured()
    if not await _login_allowed(request):
        raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, "too many login attempts")
    settings = get_settings()
    # Constant-time username compare + bcrypt password check (bcrypt verifies even on a wrong
    # username, so the response time doesn't leak which half was wrong).
    # Compare as bytes: hmac.compare_digest raises TypeError on a str with non-ASCII code points,
    # so a client sending a non-ASCII username (or a non-ASCII configured username) must not 500.
    user_ok = hmac.compare_digest(
        body.username.encode("utf-8"), settings.admin_username.encode("utf-8")
    )
    try:
        # bcrypt is ~0.3s of CPU. On the event loop that stalled the ONE process which also answers
        # the Telegram webhook and the public site — a few login attempts a second froze the bot.
        pass_ok = await asyncio.to_thread(
            verify_password, body.password, settings.admin_password_hash
        )
    except AdminNotConfigured as exc:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, _NOT_CONFIGURED) from exc
    if not (user_ok and pass_ok):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "invalid credentials")
    return TokenOut(
        access_token=create_access(settings.admin_username),
        refresh_token=create_refresh(settings.admin_username),
    )


@router.post("/refresh", response_model=TokenOut)
async def refresh(body: RefreshIn) -> TokenOut:
    try:
        payload = decode(body.refresh_token, TYPE_REFRESH)
    except AdminNotConfigured as exc:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, _NOT_CONFIGURED) from exc
    except TokenInvalid as exc:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "invalid refresh token") from exc
    # Bind the token to the CURRENT admin identity: a refresh token minted for a since-rotated
    # username must not keep renewing access (the installer reuses the JWT secret, so a username
    # change is otherwise the only lever and it wouldn't cut off old sessions without this check).
    if payload.sub != get_settings().admin_username:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "invalid refresh token")
    # The SAME login continues: carried forward, `auth_time` is what stops a chain of refreshes
    # from being a session that never ends.
    return TokenOut(
        access_token=create_access(payload.sub, auth_time=payload.auth_time),
        refresh_token=create_refresh(payload.sub, auth_time=payload.auth_time),
    )


@router.get("/me")
async def me(admin: AdminUser) -> dict[str, str]:
    return {"username": admin}
