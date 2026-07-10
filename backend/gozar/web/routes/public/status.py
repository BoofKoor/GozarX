"""Public read-only endpoints: device status + public runtime config.

``GET /status`` returns the full 'my status' view — device fields (allowance, invites, history,
cooldown) plus live panel traffic for an active device, degrading to ``live=false`` (never an error)
when the panel is unreachable. ``GET /config`` hands the SPA the public keys it needs at runtime.
"""

from __future__ import annotations

from fastapi import APIRouter, Request
from pydantic import BaseModel

from gozar.config.settings import get_settings
from gozar.db.repositories.site_claim import SiteClaimRepository
from gozar.services.settings_service import SettingsService
from gozar.services.site_trial import SiteTrialService
from gozar.web.dependencies import DbSession
from gozar.web.routes.public.identity import CurrentDevice

router = APIRouter(tags=["public"])


class StatusResponse(BaseModel):
    status: str
    active: bool
    has_config: bool
    live: bool
    data_exhausted: bool
    daily_limit: str
    daily_limit_bytes: int
    usage: str
    usage_bytes: int
    remaining: str
    cooldown: str
    can_claim: bool
    configs: int
    referral_count: int
    referral_cap: int
    streak_count: int
    streak_days: int
    location: str | None = None
    link: str | None = None


class PublicConfig(BaseModel):
    turnstile_site_key: str
    vapid_public_key: str
    turnstile_enabled: bool


def _service(request: Request, session) -> SiteTrialService:
    state = request.app.state
    return SiteTrialService(
        state.panel,
        SettingsService(session, state.redis),
        SiteClaimRepository(session),
        state.redis,
    )


@router.get("/status", response_model=StatusResponse)
async def get_status(request: Request, session: DbSession, device: CurrentDevice) -> StatusResponse:
    info = await _service(request, session).status(device)
    return StatusResponse(**vars(info))


@router.get("/config", response_model=PublicConfig)
async def get_config() -> PublicConfig:
    settings = get_settings()
    return PublicConfig(
        turnstile_site_key=settings.turnstile_site_key,
        vapid_public_key=settings.vapid_public_key,
        turnstile_enabled=bool(settings.turnstile_secret.get_secret_value()),
    )
