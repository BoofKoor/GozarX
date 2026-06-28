"""Runtime settings (auth-gated) — read/update the editable economics in the ``settings`` table.

Only product knobs are exposed here; infra secrets live in env and are never returned. Reuses
``SettingsService`` (Redis-cached) so a write invalidates the bot's cache immediately.
"""

from __future__ import annotations

import json

from fastapi import APIRouter, Request
from pydantic import BaseModel

from gozar.services.settings_service import SettingKey, SettingsService
from gozar.web.dependencies import AdminUser, DbSession

router = APIRouter(prefix="/settings", tags=["settings"])


def _settings(request: Request, session: object) -> SettingsService:
    return SettingsService(session, request.app.state.redis)  # type: ignore[arg-type]


class SettingsOut(BaseModel):
    trial_squad: str | None
    locations: list[str]
    daily_limit_mb: int
    referral_reward_mb: int
    referral_reward_limit: int
    trial_hours: int
    ads_enabled: bool
    configs_per_page: int


class SettingsPatch(BaseModel):
    locations: list[str] | None = None
    daily_limit_mb: int | None = None
    referral_reward_mb: int | None = None
    referral_reward_limit: int | None = None
    trial_hours: int | None = None
    ads_enabled: bool | None = None
    configs_per_page: int | None = None


async def _read(settings: SettingsService) -> SettingsOut:
    return SettingsOut(
        trial_squad=await settings.get(SettingKey.TRIAL_SQUAD),
        locations=await settings.get_list(SettingKey.LOCATIONS),
        daily_limit_mb=await settings.get_int(SettingKey.DAILY_LIMIT_MB, 1024),
        referral_reward_mb=await settings.get_int(SettingKey.REFERRAL_REWARD_MB, 0),
        referral_reward_limit=await settings.get_int(SettingKey.REFERRAL_REWARD_LIMIT, 0),
        trial_hours=await settings.get_int(SettingKey.TRIAL_HOURS, 24),
        ads_enabled=await settings.get_bool(SettingKey.ADS_ENABLED),
        configs_per_page=await settings.get_int(SettingKey.CONFIGS_PER_PAGE, 8),
    )


@router.get("/", response_model=SettingsOut)
async def get_settings_endpoint(
    request: Request, session: DbSession, admin: AdminUser
) -> SettingsOut:
    return await _read(_settings(request, session))


@router.put("/", response_model=SettingsOut)
async def update_settings(
    body: SettingsPatch, request: Request, session: DbSession, admin: AdminUser
) -> SettingsOut:
    settings = _settings(request, session)
    if body.locations is not None:
        await settings.set(SettingKey.LOCATIONS, json.dumps(body.locations))
    if body.daily_limit_mb is not None:
        await settings.set(SettingKey.DAILY_LIMIT_MB, str(body.daily_limit_mb))
    if body.referral_reward_mb is not None:
        await settings.set(SettingKey.REFERRAL_REWARD_MB, str(body.referral_reward_mb))
    if body.referral_reward_limit is not None:
        await settings.set(SettingKey.REFERRAL_REWARD_LIMIT, str(body.referral_reward_limit))
    if body.trial_hours is not None:
        await settings.set(SettingKey.TRIAL_HOURS, str(body.trial_hours))
    if body.ads_enabled is not None:
        await settings.set(SettingKey.ADS_ENABLED, "true" if body.ads_enabled else "false")
    if body.configs_per_page is not None:
        await settings.set(SettingKey.CONFIGS_PER_PAGE, str(max(1, body.configs_per_page)))
    return await _read(settings)
