"""Public claim endpoints: GET /locations (the picker) + POST /claim (provision + deliver).

``/claim`` is guarded by a Redis rate limit + Turnstile, then reuses ``SiteTrialService`` (which
reuses the panel client + pure trial helpers). Domain outcomes (cooldown / not-ready / no-locations
/ panel-error) return **200 with ok=false + a reason** so the SPA can render the designed state
screens; only the security guards (rate limit / Turnstile) return 4xx.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from gozar.cache.redis import single_flight
from gozar.db.repositories.site_claim import SiteClaimRepository
from gozar.db.repositories.site_device import SiteDeviceRepository
from gozar.db.repositories.site_reward import SiteRewardRepository
from gozar.services.settings_service import SettingsService
from gozar.services.site_referral import SiteReferralService
from gozar.services.site_trial import (
    AlreadyClaimedToday,
    Delivered,
    NoLocations,
    NotReady,
    PanelError,
    SiteTrialService,
)
from gozar.web.dependencies import DbSession
from gozar.web.routes.public.identity import CurrentDevice, client_ip
from gozar.web.routes.public.security import rate_limit_ok, verify_turnstile

router = APIRouter(tags=["public"])

# Generous per-device window — blocks scripted abuse without ever tripping a real user. A per-IP
# backstop is ESSENTIAL here: a cookieless client is minted a FRESH device (uuid) each request, so
# the per-device limit alone never bites it — and /claim provisions a live panel account, so an
# uncapped cookieless loop would mint unbounded accounts. The IP window is generous (shared NATs)
# but far below what a provisioning loop needs.
_CLAIM_LIMIT = 10
_CLAIM_WINDOW = 60
_CLAIM_IP_LIMIT = 40
_CLAIM_IP_WINDOW = 60


class LocationsResponse(BaseModel):
    locations: list[str]


class ClaimRequest(BaseModel):
    location: str
    turnstile_token: str | None = None


class ClaimResponse(BaseModel):
    ok: bool
    reason: str | None = None
    location: str | None = None
    link: str | None = None
    expires: str | None = None
    size: str | None = None
    changed: bool = False
    retry_after: str | None = None


def _service(request: Request, session) -> SiteTrialService:
    state = request.app.state
    return SiteTrialService(
        state.panel,
        SettingsService(session, state.redis),
        SiteClaimRepository(session),
        SiteRewardRepository(session),
        state.redis,
    )


async def _maybe_credit_referrer(request: Request, session, device) -> None:
    """On a device's FIRST-ever claim, credit its referrer (in the same session, so the +1 commits
    with the claim). Best-effort — a missing/self/blocked referrer is simply not credited."""
    if await SiteClaimRepository(session).count_for_device(device.uuid) != 1:
        return
    state = request.app.state
    referral = SiteReferralService(
        SiteDeviceRepository(session),
        SiteRewardRepository(session),
        SettingsService(session, state.redis),
        state.panel,
        state.redis,
    )
    await referral.award_first_claim(device)


@router.get("/locations", response_model=LocationsResponse)
async def get_locations(
    request: Request, session: DbSession, device: CurrentDevice
) -> LocationsResponse:
    result = await _service(request, session).available_locations(device)
    if isinstance(result, PanelError):
        raise HTTPException(status_code=502, detail="panel_error")
    return LocationsResponse(locations=result)


@router.post("/claim", response_model=ClaimResponse)
async def post_claim(
    body: ClaimRequest, request: Request, session: DbSession, device: CurrentDevice
) -> ClaimResponse:
    redis = request.app.state.redis
    per_device = await rate_limit_ok(
        redis, "claim", device.uuid, limit=_CLAIM_LIMIT, window_seconds=_CLAIM_WINDOW
    )
    per_ip = await rate_limit_ok(
        redis,
        "claim_ip",
        client_ip(request),
        limit=_CLAIM_IP_LIMIT,
        window_seconds=_CLAIM_IP_WINDOW,
    )
    if not per_device or not per_ip:
        raise HTTPException(status_code=429, detail="rate_limited")

    http = getattr(request.app.state, "http", None)
    if not await verify_turnstile(http, body.turnstile_token or "", client_ip(request)):
        raise HTTPException(status_code=403, detail="turnstile_failed")

    # Serialize concurrent claims for THIS device (double-tap / two tabs). Without it both requests
    # read the same stale cooldown under READ COMMITTED, both provision a panel account, and the
    # referral credit runs twice. A loser gets 429 (the SPA retries) rather than a 2nd account.
    async with single_flight(redis, "claim_lock", device.uuid, ttl_seconds=30) as first:
        if not first:
            raise HTTPException(status_code=429, detail="rate_limited")
        result = await _service(request, session).claim(device, body.location)
        if isinstance(result, Delivered):
            if not result.changed:
                await _maybe_credit_referrer(request, session, device)
            return ClaimResponse(
                ok=True,
                location=result.location,
                link=result.link,
                expires=result.expires,
                size=result.size,
                changed=result.changed,
            )
        if isinstance(result, AlreadyClaimedToday):
            return ClaimResponse(ok=False, reason="cooldown", retry_after=result.retry_after)
        if isinstance(result, NotReady):
            return ClaimResponse(ok=False, reason="not_ready")
        if isinstance(result, NoLocations):
            return ClaimResponse(ok=False, reason="no_locations")
        return ClaimResponse(ok=False, reason="panel_error")
