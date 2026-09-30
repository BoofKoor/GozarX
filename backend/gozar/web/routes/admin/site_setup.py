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
from gozar.web.routes.admin.bounds import (
    DailyLimitMb,
    RewardLimit,
    RewardMb,
    StreakDays,
    TrialHours,
)
from gozar.web.routes.admin.site_locations import reject_unknown_locations, reject_unknown_squad

logger = logging.getLogger("gozar.web.admin.site_setup")
router = APIRouter(prefix="/site/setup", tags=["site-setup"])


def _settings(request: Request, session: object) -> SettingsService:
    return SettingsService(session, request.app.state.redis)  # type: ignore[arg-type]


class SiteSetupStatusOut(BaseModel):
    completed: bool


class SiteSetupIn(BaseModel):
    trial_squad: str
    # Explicit allowlist (a subset of the squad's names); empty ⇒ every squad location, live.
    locations: list[str] = Field(default_factory=list)
    trial_hours: TrialHours = 24
    daily_limit_mb: DailyLimitMb = 1024
    referral_reward_mb: RewardMb = 500
    referral_reward_limit: RewardLimit = 10
    reward_pwa_mb: RewardMb = 200
    reward_push_mb: RewardMb = 200
    reward_streak_mb: RewardMb = 200
    streak_days: StreakDays = 3


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

    # An EXPLICIT allowlist is validated against the squad being saved, exactly like the settings
    # PUT does. Without this the wizard was a hole straight through that check: a typo (or a name
    # left over from another squad) was stored, offered on the public picker, and picking it handed
    # the visitor a config for a different country — the v1 index-mismatch lesson in a new shape.
    await reject_unknown_squad(request, body.trial_squad)
    await reject_unknown_locations(request, body.trial_squad, body.locations)

    # No explicit allowlist means ALL of the squad's locations, stored as [] so a host added later
    # appears on its own. It used to store a snapshot of every name at wizard time instead, which
    # the site then ignored anyway (it always read the live list) — and which went stale the moment
    # a host was hidden or renamed, blocking every later save with a 400 for a name no checkbox
    # showed. The squad is still checked to serve something: a squad with no enabled host is the
    # one outcome the operator should hear about now rather than from an empty site.
    if not body.locations:
        try:
            live = await request.app.state.panel.squad_location_names(body.trial_squad)
        except RemnawaveError as exc:
            logger.warning("site setup: squad_location_names failed")
            raise HTTPException(
                status.HTTP_502_BAD_GATEWAY, "panel unreachable — cannot check the squad's hosts"
            ) from exc
        if not live:
            raise HTTPException(
                status.HTTP_409_CONFLICT, "squad matched no enabled host — check the squad's hosts"
            )
    await settings.set(SiteSettingKey.SITE_TRIAL_SQUAD, body.trial_squad)
    await settings.set(SiteSettingKey.SITE_LOCATIONS, json.dumps(body.locations))

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
