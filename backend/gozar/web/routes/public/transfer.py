"""Public device-transfer endpoints: POST /transfer/create + POST /transfer/redeem.

Account-less cross-device continuity. ``/create`` (on the source device) mints a one-time code;
``/redeem`` (on a new browser) consumes it and re-points the signed device cookie to the source
device — the new browser then IS that device. Both are rate-limited. ``/redeem`` is limited by
client IP because the caller has no trusted identity yet: that limit plus the 10-minute expiry and
the large code space is the brute-force guard, so no Turnstile is needed. Domain failures return
200 + ok=false (the SPA renders the designed states); only the rate limit raises (429).
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request, Response
from pydantic import BaseModel

from gozar.db.repositories.site_device import SiteDeviceRepository
from gozar.services.site_transfer import SiteTransferService
from gozar.web.dependencies import DbSession
from gozar.web.routes.public.identity import CurrentDevice, client_ip, set_device_cookie
from gozar.web.routes.public.security import rate_limit_ok

router = APIRouter(tags=["public"])

# A handful of codes per 10-min window per device — plenty for regenerating an expired one. A per-IP
# backstop caps a cookieless client (minted a fresh device per request, so the per-device limit
# never bites) from spinning up transfer codes in a loop.
_CREATE_LIMIT = 5
_CREATE_WINDOW = 600
_CREATE_IP_LIMIT = 20
# Brute-force guard on the 8-char code — per client IP (the redeemer has no device trust yet).
_REDEEM_LIMIT = 10
_REDEEM_WINDOW = 300


class TransferCreateResponse(BaseModel):
    ok: bool
    reason: str | None = None
    code: str | None = None
    expires_in: int | None = None


class RedeemRequest(BaseModel):
    code: str


class RedeemResponse(BaseModel):
    ok: bool
    reason: str | None = None
    has_config: bool = False
    referral_count: int = 0


def _service(request: Request, session) -> SiteTransferService:
    return SiteTransferService(SiteDeviceRepository(session), request.app.state.redis)


@router.post("/transfer/create", response_model=TransferCreateResponse)
async def create_transfer(
    request: Request, session: DbSession, device: CurrentDevice
) -> TransferCreateResponse:
    redis = request.app.state.redis
    per_device = await rate_limit_ok(
        redis, "transfer_create", device.uuid, limit=_CREATE_LIMIT, window_seconds=_CREATE_WINDOW
    )
    per_ip = await rate_limit_ok(
        redis,
        "transfer_create_ip",
        client_ip(request),
        limit=_CREATE_IP_LIMIT,
        window_seconds=_CREATE_WINDOW,
    )
    if not per_device or not per_ip:
        raise HTTPException(status_code=429, detail="rate_limited")

    code = await _service(request, session).create_code(device)
    if code is None:
        return TransferCreateResponse(ok=False, reason="try_again")
    return TransferCreateResponse(ok=True, code=code.code, expires_in=code.expires_in)


@router.post("/transfer/redeem", response_model=RedeemResponse)
async def redeem_transfer(
    body: RedeemRequest, request: Request, response: Response, session: DbSession
) -> RedeemResponse:
    # No CurrentDevice dependency here: the whole point is to REPLACE identity, and minting one via
    # the dependency would emit a competing Set-Cookie. We set the source cookie ourselves below.
    redis = request.app.state.redis
    if not await rate_limit_ok(
        redis,
        "transfer_redeem",
        client_ip(request),
        limit=_REDEEM_LIMIT,
        window_seconds=_REDEEM_WINDOW,
    ):
        raise HTTPException(status_code=429, detail="rate_limited")

    result = await _service(request, session).redeem(body.code)
    if result is None:
        return RedeemResponse(ok=False, reason="invalid")
    set_device_cookie(response, request, result.device_uuid)
    return RedeemResponse(
        ok=True, has_config=result.has_config, referral_count=result.referral_count
    )
