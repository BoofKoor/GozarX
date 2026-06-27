"""First-run setup wizard (auth-gated).

GozarX's admin credentials come from env (installer-generated), so — unlike marzbot — the wizard
needs no separate credential bootstrap: the admin logs in, then configures the *product* settings in
the DB. "Setup completed" simply means the trial squad has been chosen. Subsequent edits go through
the Settings endpoints.
"""

from __future__ import annotations

import json

from fastapi import APIRouter, HTTPException, Request, status
from pydantic import BaseModel, Field

from gozar.remnawave import RemnawaveError
from gozar.services.settings_service import SettingKey, SettingsService
from gozar.web.dependencies import AdminUser, DbSession

router = APIRouter(prefix="/setup", tags=["setup"])


def _settings(request: Request, session: object) -> SettingsService:
    return SettingsService(session, request.app.state.redis)  # type: ignore[arg-type]


class SetupStatusOut(BaseModel):
    completed: bool


class SquadOut(BaseModel):
    uuid: str
    name: str


class SetupIn(BaseModel):
    trial_squad: str
    locations: list[str] = Field(default_factory=list)
    daily_limit_mb: int = 1024
    referral_reward_mb: int = 500
    referral_reward_limit: int = 10
    trial_hours: int = 24
    ads_enabled: bool = False


@router.get("/status", response_model=SetupStatusOut)
async def setup_status(request: Request, session: DbSession, admin: AdminUser) -> SetupStatusOut:
    squad = await _settings(request, session).get(SettingKey.TRIAL_SQUAD)
    return SetupStatusOut(completed=bool(squad))


@router.get("/squads", response_model=list[SquadOut])
async def list_squads(request: Request, admin: AdminUser) -> list[SquadOut]:
    """The panel's internal squads — the wizard picks one as the trial squad."""
    try:
        squads = await request.app.state.panel.list_internal_squads()
    except RemnawaveError as exc:
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, "panel unreachable") from exc
    return [SquadOut(uuid=s.uuid, name=s.name) for s in squads]


@router.post("/")
async def complete_setup(
    body: SetupIn, request: Request, session: DbSession, admin: AdminUser
) -> SetupStatusOut:
    settings = _settings(request, session)
    await settings.set(SettingKey.TRIAL_SQUAD, body.trial_squad)
    await settings.set(SettingKey.LOCATIONS, json.dumps(body.locations))
    await settings.set(SettingKey.DAILY_LIMIT_MB, str(body.daily_limit_mb))
    await settings.set(SettingKey.REFERRAL_REWARD_MB, str(body.referral_reward_mb))
    await settings.set(SettingKey.REFERRAL_REWARD_LIMIT, str(body.referral_reward_limit))
    await settings.set(SettingKey.TRIAL_HOURS, str(body.trial_hours))
    await settings.set(SettingKey.ADS_ENABLED, "true" if body.ads_enabled else "false")
    return SetupStatusOut(completed=True)
