"""Admin auth endpoints: login, refresh, me.

Single admin from env (``admin_username`` + bcrypt ``admin_password_hash`` + ``admin_jwt_secret``).
503 when the panel isn't configured yet; 401 on a credential/token mismatch.
"""

from __future__ import annotations

import hmac

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel

from gozar.config.settings import get_settings
from gozar.web.auth import AdminNotConfigured, TokenInvalid
from gozar.web.auth.jwt import TYPE_REFRESH, create_access, create_refresh, decode
from gozar.web.auth.passwords import verify_password
from gozar.web.dependencies import AdminUser

router = APIRouter(prefix="/auth", tags=["auth"])

_NOT_CONFIGURED = "admin panel not configured"


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


@router.post("/login", response_model=TokenOut)
async def login(body: LoginIn) -> TokenOut:
    _require_configured()
    settings = get_settings()
    # Constant-time username compare + bcrypt password check (bcrypt verifies even on a wrong
    # username, so the response time doesn't leak which half was wrong).
    user_ok = hmac.compare_digest(body.username, settings.admin_username)
    try:
        pass_ok = verify_password(body.password, settings.admin_password_hash)
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
    return TokenOut(
        access_token=create_access(payload.sub),
        refresh_token=create_refresh(payload.sub),
    )


@router.get("/me")
async def me(admin: AdminUser) -> dict[str, str]:
    return {"username": admin}
