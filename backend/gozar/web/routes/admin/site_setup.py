"""Website first-run setup wizard (auth-gated).

Mirrors ``admin/setup.py`` for the site economy: pick the site trial squad, set the economy numbers,
and derive ``SITE_LOCATIONS`` from the squad's remark NAMES (the v1 index-mismatch lesson). Squad
options come from the existing ``/admin/setup/squads``; ``GET /site/setup/locations`` returns a
squad's derivable names for the wizard picker.
"""

from __future__ import annotations

import json
import logging

from fastapi import APIRouter, HTTPException, Request, status
from pydantic import BaseModel, Field

from gozar.remnawave import RemnawaveError
from gozar.services.settings_service import SettingsService, SiteSettingKey
from gozar.web.dependencies import AdminUser, DbSession

logger = logging.getLogger("gozar.web.admin.site_setup")
router = APIRouter(prefix="/site/setup", tags=["site-setup"])


def _settings(request: Request, session: object) -> SettingsService:
    return SettingsService(session, request.app.state.redis)  # type: ignore[arg-type]


class SiteSetupStatusOut(BaseModel):
    completed: bool


class SiteSetupIn(BaseModel):
    trial_squad: str
    # Explicit allowlist (a subset of the squad's names); empty ⇒ derive every squad location.
    locations: list[str] = Field(default_factory=list)
    trial_hours: int = 24
    daily_limit_mb: int = 1024
    referral_reward_mb: int = 500
    referral_reward_limit: int = 10
    reward_pwa_mb: int = 200
    reward_push_mb: int = 200
    reward_streak_mb: int = 200
    streak_days: int = 3


@router.get("/status", response_model=SiteSetupStatusOut)
async def site_setup_status(
    request: Request, session: DbSession, admin: AdminUser
) -> SiteSetupStatusOut:
    squad = await _settings(request, session).get(SiteSettingKey.SITE_TRIAL_SQUAD)
    return SiteSetupStatusOut(completed=bool(squad))


@router.get("/locations", response_model=list[str])
async def derivable_locations(squad: str, request: Request, admin: AdminUser) -> list[str]:
    """A squad's location remark NAMES — the wizard's picker options."""
    try:
        return await request.app.state.panel.squad_location_names(squad)
    except RemnawaveError as exc:
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, "panel unreachable") from exc


@router.post("/", response_model=SiteSetupStatusOut)
async def complete_site_setup(
    body: SiteSetupIn, request: Request, session: DbSession, admin: AdminUser
) -> SiteSetupStatusOut:
    settings = _settings(request, session)
    await settings.set(SiteSettingKey.SITE_TRIAL_SQUAD, body.trial_squad)

    # No explicit allowlist? derive every location from the squad's remark names. Storing an empty
    # list here used to be the silent outcome of a panel hiccup, and it is the worst possible state:
    # new visitors saw an empty picker while the claim-time filter read the same [] as "no
    # filtering". Fail the wizard loudly instead — the operator can retry once the panel answers.
    locations = body.locations
    if not locations:
        try:
            locations = await request.app.state.panel.squad_location_names(body.trial_squad)
        except RemnawaveError as exc:
            logger.warning("site setup: squad_location_names failed")
            raise HTTPException(
                status.HTTP_502_BAD_GATEWAY, "panel unreachable — cannot derive locations"
            ) from exc
        if not locations:
            raise HTTPException(
                status.HTTP_409_CONFLICT, "squad matched no enabled host — check the squad's hosts"
            )
    await settings.set(SiteSettingKey.SITE_LOCATIONS, json.dumps(locations))

    await settings.set(SiteSettingKey.SITE_TRIAL_HOURS, str(max(1, body.trial_hours)))
    await settings.set(SiteSettingKey.SITE_DAILY_LIMIT_MB, str(max(0, body.daily_limit_mb)))
    await settings.set(SiteSettingKey.SITE_REFERRAL_REWARD_MB, str(max(0, body.referral_reward_mb)))
    await settings.set(
        SiteSettingKey.SITE_REFERRAL_REWARD_LIMIT, str(max(0, body.referral_reward_limit))
    )
    await settings.set(SiteSettingKey.SITE_REWARD_PWA_MB, str(max(0, body.reward_pwa_mb)))
    await settings.set(SiteSettingKey.SITE_REWARD_PUSH_MB, str(max(0, body.reward_push_mb)))
    await settings.set(SiteSettingKey.SITE_REWARD_STREAK_MB, str(max(0, body.reward_streak_mb)))
    await settings.set(SiteSettingKey.SITE_STREAK_DAYS, str(max(0, body.streak_days)))
    return SiteSetupStatusOut(completed=True)
