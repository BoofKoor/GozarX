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
from gozar.db.repositories.site_reward import SiteRewardRepository
from gozar.services.settings_service import SettingsService, SiteSettingKey
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
    streak_active: bool  # streak_count has reached streak_days (the daily-claim bonus is standing)
    trial_hours: int  # rolling window each config lasts / renews on ("renews every Nh")
    location: str | None = None
    link: str | None = None
    handle: str  # this device's public account id (GZ-…) — shown on the account page
    ref_code: str  # this device's referral code (its handle) — SPA builds "?ref=<ref_code>" links


class PublicConfig(BaseModel):
    turnstile_site_key: str
    vapid_public_key: str
    turnstile_enabled: bool
    popular_location: str | None = None  # remark NAME the admin flags as "popular" (picker star)
    # Reward MB amounts + streak length (from site_* settings) so the SPA can show "+N MB" chips and
    # the streak day-dots without hardcoding any economics.
    reward_pwa_mb: int = 0
    reward_push_mb: int = 0
    reward_streak_mb: int = 0
    streak_days: int = 0


def _service(request: Request, session) -> SiteTrialService:
    state = request.app.state
    return SiteTrialService(
        state.panel,
        SettingsService(session, state.redis),
        SiteClaimRepository(session),
        SiteRewardRepository(session),
        state.redis,
    )


@router.get("/status", response_model=StatusResponse)
async def get_status(request: Request, session: DbSession, device: CurrentDevice) -> StatusResponse:
    info = await _service(request, session).status(device)
    handle = device.handle or device.uuid  # uuid fallback for any pre-migration row
    return StatusResponse(**vars(info), handle=handle, ref_code=handle)


@router.get("/config", response_model=PublicConfig)
async def get_config(request: Request, session: DbSession) -> PublicConfig:
    settings = get_settings()
    site_settings = SettingsService(session, request.app.state.redis)
    popular = await site_settings.get(SiteSettingKey.SITE_POPULAR_LOCATION)
    return PublicConfig(
        turnstile_site_key=settings.turnstile_site_key,
        vapid_public_key=settings.vapid_public_key,
        turnstile_enabled=bool(settings.turnstile_secret.get_secret_value()),
        popular_location=popular or None,
        reward_pwa_mb=await site_settings.get_int(SiteSettingKey.SITE_REWARD_PWA_MB, 0),
        reward_push_mb=await site_settings.get_int(SiteSettingKey.SITE_REWARD_PUSH_MB, 0),
        reward_streak_mb=await site_settings.get_int(SiteSettingKey.SITE_REWARD_STREAK_MB, 0),
        streak_days=await site_settings.get_int(SiteSettingKey.SITE_STREAK_DAYS, 0),
    )
