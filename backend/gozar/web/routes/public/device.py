"""Public device-lifecycle endpoint: POST /device/reset — the danger-row wipe.

Irreversibly erases THIS browser's device (history, volume, invites), frees its panel trial, and
clears the identity cookie so the browser starts fresh. Like /transfer/redeem, this resolves the
device from the cookie MANUALLY (no ``CurrentDevice`` dependency) — the endpoint destroys identity,
so minting a throwaway device via the dependency would be pointless and would emit a competing
Set-Cookie. Rate-limited; no Turnstile (it only ever affects the caller's own device).
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request, Response
from pydantic import BaseModel

from gozar.config.settings import get_settings
from gozar.db.repositories.site_device import SiteDeviceRepository
from gozar.services.site_device import SiteDeviceService
from gozar.web.dependencies import DbSession
from gozar.web.routes.public.identity import (
    DEVICE_COOKIE,
    clear_device_cookie,
    client_ip,
    verify_device_cookie,
)
from gozar.web.routes.public.security import rate_limit_ok

router = APIRouter(tags=["public"])

_RESET_LIMIT = 5
_RESET_WINDOW = 600


class ResetResponse(BaseModel):
    ok: bool


@router.post("/device/reset", response_model=ResetResponse)
async def reset_device(request: Request, response: Response, session: DbSession) -> ResetResponse:
    redis = request.app.state.redis
    secret = get_settings().site_cookie_secret.get_secret_value()
    device_uuid = verify_device_cookie(request.cookies.get(DEVICE_COOKIE, ""), secret)

    # Rate-limit by the cookie's device when present, else by IP (a cookieless caller has nothing
    # to reset but still shouldn't be able to hammer the endpoint).
    if not await rate_limit_ok(
        redis,
        "device_reset",
        device_uuid or client_ip(request),
        limit=_RESET_LIMIT,
        window_seconds=_RESET_WINDOW,
    ):
        raise HTTPException(status_code=429, detail="rate_limited")

    if device_uuid is not None:
        device = await SiteDeviceRepository(session).get(device_uuid)
        if device is not None:
            await SiteDeviceService(
                SiteDeviceRepository(session), request.app.state.panel, redis
            ).reset(device)

    # Always clear the cookie — the caller ends up with a clean slate whether or not a row existed.
    clear_device_cookie(response)
    return ResetResponse(ok=True)
