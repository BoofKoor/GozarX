"""FastAPI dependencies for the admin API.

``get_db`` opens one ``AsyncSession`` per request from ``app.state.sessionmaker`` (commit on
success, rollback on error) — the request-scoped analogue of the bot's per-update middleware.
``require_admin`` gates a route on a valid **access** JWT and returns the admin username (``sub``).
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Annotated

from fastapi import Depends, Header, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from gozar.config.settings import get_settings
from gozar.web.auth import AdminNotConfigured, TokenInvalid
from gozar.web.auth.jwt import TYPE_ACCESS, decode


async def get_db(request: Request) -> AsyncIterator[AsyncSession]:
    sessionmaker = request.app.state.sessionmaker
    async with sessionmaker() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


DbSession = Annotated[AsyncSession, Depends(get_db)]


def _bearer(authorization: str | None) -> str | None:
    if not authorization:
        return None
    parts = authorization.split(None, 1)
    if len(parts) != 2 or parts[0].lower() != "bearer":
        return None
    return parts[1].strip()


async def require_admin(
    authorization: Annotated[str | None, Header()] = None,
) -> str:
    token = _bearer(authorization)
    if not token:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "missing bearer token")
    try:
        payload = decode(token, TYPE_ACCESS)
    except AdminNotConfigured as exc:
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE, "admin panel not configured"
        ) from exc
    except TokenInvalid as exc:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "invalid token") from exc
    # Reject a token whose subject is no longer the configured admin (identity rotated).
    if payload.sub != get_settings().admin_username:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "invalid token")
    return payload.sub


AdminUser = Annotated[str, Depends(require_admin)]
