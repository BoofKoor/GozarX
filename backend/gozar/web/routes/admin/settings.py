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
    ad_button_enabled: bool
    ad_button_text: str
    ad_button_url: str
    ad_button_emoji_id: str


class SettingsPatch(BaseModel):
    locations: list[str] | None = None
    daily_limit_mb: int | None = None
    referral_reward_mb: int | None = None
    referral_reward_limit: int | None = None
    trial_hours: int | None = None
    ads_enabled: bool | None = None
    configs_per_page: int | None = None
    ad_button_enabled: bool | None = None
    ad_button_text: str | None = None
    ad_button_url: str | None = None
    ad_button_emoji_id: str | None = None


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
        ad_button_enabled=await settings.get_bool(SettingKey.AD_BUTTON_ENABLED),
        ad_button_text=await settings.get(SettingKey.AD_BUTTON_TEXT) or "",
        ad_button_url=await settings.get(SettingKey.AD_BUTTON_URL) or "",
        ad_button_emoji_id=await settings.get(SettingKey.AD_BUTTON_EMOJI_ID) or "",
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
    # Floor the numerics (mirrors site_settings): a negative daily_limit_mb makes compute_traffic_
    # bytes return a negative byte count, which the panel rejects — so every claim fails with a
    # PanelError until the value is fixed. trial_hours floors to 1; the rest to 0.
    if body.daily_limit_mb is not None:
        await settings.set(SettingKey.DAILY_LIMIT_MB, str(max(0, body.daily_limit_mb)))
    if body.referral_reward_mb is not None:
        await settings.set(SettingKey.REFERRAL_REWARD_MB, str(max(0, body.referral_reward_mb)))
    if body.referral_reward_limit is not None:
        await settings.set(
            SettingKey.REFERRAL_REWARD_LIMIT, str(max(0, body.referral_reward_limit))
        )
    if body.trial_hours is not None:
        await settings.set(SettingKey.TRIAL_HOURS, str(max(1, body.trial_hours)))
    if body.ads_enabled is not None:
        await settings.set(SettingKey.ADS_ENABLED, "true" if body.ads_enabled else "false")
    if body.configs_per_page is not None:
        await settings.set(SettingKey.CONFIGS_PER_PAGE, str(max(1, body.configs_per_page)))
    if body.ad_button_enabled is not None:
        await settings.set(
            SettingKey.AD_BUTTON_ENABLED, "true" if body.ad_button_enabled else "false"
        )
    if body.ad_button_text is not None:
        await settings.set(SettingKey.AD_BUTTON_TEXT, body.ad_button_text.strip())
    if body.ad_button_url is not None:
        await settings.set(SettingKey.AD_BUTTON_URL, body.ad_button_url.strip())
    if body.ad_button_emoji_id is not None:
        await settings.set(SettingKey.AD_BUTTON_EMOJI_ID, body.ad_button_emoji_id.strip())
    return await _read(settings)
