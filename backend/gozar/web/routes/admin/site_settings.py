"""Website runtime settings (auth-gated) — read/update the ``site_*`` economy.

The mirror of ``admin/settings.py`` for the site's own economy (``SiteSettingKey``). The trial squad
+ the location allowlist are set in the site setup wizard; the economy numbers are edited here.
A write invalidates the shared settings cache so the public site picks it up immediately.
"""

from __future__ import annotations

import json
import logging

from fastapi import APIRouter, HTTPException, Request, status
from pydantic import BaseModel

from gozar.remnawave import RemnawaveError
from gozar.remnawave.links import normalize_remark
from gozar.services.settings_service import SettingsService, SiteSettingKey
from gozar.web.dependencies import AdminUser, DbSession

logger = logging.getLogger("gozar.web.admin")

router = APIRouter(prefix="/site/settings", tags=["site-settings"])


def _settings(request: Request, session: object) -> SettingsService:
    return SettingsService(session, request.app.state.redis)  # type: ignore[arg-type]


class SiteSettingsOut(BaseModel):
    trial_squad: str | None
    locations: list[str]
    popular_location: str | None
    trial_hours: int
    daily_limit_mb: int
    referral_reward_mb: int
    referral_reward_limit: int
    reward_pwa_mb: int
    reward_push_mb: int
    reward_streak_mb: int
    streak_days: int


class SiteSettingsPatch(BaseModel):
    locations: list[str] | None = None
    popular_location: str | None = None  # "" clears it; None leaves it unchanged
    trial_hours: int | None = None
    daily_limit_mb: int | None = None
    referral_reward_mb: int | None = None
    referral_reward_limit: int | None = None
    reward_pwa_mb: int | None = None
    reward_push_mb: int | None = None
    reward_streak_mb: int | None = None
    streak_days: int | None = None


async def _read(settings: SettingsService) -> SiteSettingsOut:
    return SiteSettingsOut(
        trial_squad=await settings.get(SiteSettingKey.SITE_TRIAL_SQUAD),
        locations=await settings.get_list(SiteSettingKey.SITE_LOCATIONS),
        popular_location=await settings.get(SiteSettingKey.SITE_POPULAR_LOCATION),
        trial_hours=await settings.get_int(SiteSettingKey.SITE_TRIAL_HOURS, 24),
        daily_limit_mb=await settings.get_int(SiteSettingKey.SITE_DAILY_LIMIT_MB, 1024),
        referral_reward_mb=await settings.get_int(SiteSettingKey.SITE_REFERRAL_REWARD_MB, 0),
        referral_reward_limit=await settings.get_int(SiteSettingKey.SITE_REFERRAL_REWARD_LIMIT, 0),
        reward_pwa_mb=await settings.get_int(SiteSettingKey.SITE_REWARD_PWA_MB, 0),
        reward_push_mb=await settings.get_int(SiteSettingKey.SITE_REWARD_PUSH_MB, 0),
        reward_streak_mb=await settings.get_int(SiteSettingKey.SITE_REWARD_STREAK_MB, 0),
        streak_days=await settings.get_int(SiteSettingKey.SITE_STREAK_DAYS, 0),
    )


# Numeric field -> (setting key, min floor). Stored as strings; trial_hours floored to 1, rest to 0.
_NUM_FIELDS = (
    ("trial_hours", SiteSettingKey.SITE_TRIAL_HOURS, 1),
    ("daily_limit_mb", SiteSettingKey.SITE_DAILY_LIMIT_MB, 0),
    ("referral_reward_mb", SiteSettingKey.SITE_REFERRAL_REWARD_MB, 0),
    ("referral_reward_limit", SiteSettingKey.SITE_REFERRAL_REWARD_LIMIT, 0),
    ("reward_pwa_mb", SiteSettingKey.SITE_REWARD_PWA_MB, 0),
    ("reward_push_mb", SiteSettingKey.SITE_REWARD_PUSH_MB, 0),
    ("reward_streak_mb", SiteSettingKey.SITE_REWARD_STREAK_MB, 0),
    ("streak_days", SiteSettingKey.SITE_STREAK_DAYS, 0),
)


@router.get("/", response_model=SiteSettingsOut)
async def get_site_settings(
    request: Request, session: DbSession, admin: AdminUser
) -> SiteSettingsOut:
    return await _read(_settings(request, session))


async def _reject_unknown_locations(
    request: Request, settings: SettingsService, wanted: list[str]
) -> None:
    """400 on any name the configured squad doesn't serve — matched by NORMALISED name.

    The box used to accept anything, so a typo or a name left over from another squad was stored
    and offered to visitors; picking it then produced a config for a different country. Validation
    is best-effort by design: with no squad set, or the panel unreachable, we store what the admin
    typed rather than blocking them during an outage.
    """
    squad = await settings.get(SiteSettingKey.SITE_TRIAL_SQUAD)
    if not squad:
        return
    try:
        known = await request.app.state.panel.squad_location_names(squad)
    except RemnawaveError:
        logger.warning("locations not validated — panel unreachable")
        return
    if not known:
        return
    allowed = {normalize_remark(name) for name in known}
    unknown = [name for name in wanted if normalize_remark(name) not in allowed]
    if unknown:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            f"not served by the squad: {', '.join(unknown)} — available: {', '.join(known)}",
        )


@router.put("/", response_model=SiteSettingsOut)
async def update_site_settings(
    body: SiteSettingsPatch, request: Request, session: DbSession, admin: AdminUser
) -> SiteSettingsOut:
    settings = _settings(request, session)
    if body.locations is not None:
        await _reject_unknown_locations(request, settings, body.locations)
        await settings.set(SiteSettingKey.SITE_LOCATIONS, json.dumps(body.locations))
    if body.popular_location is not None:
        # empty string clears the flag (no popular location)
        await settings.set(SiteSettingKey.SITE_POPULAR_LOCATION, body.popular_location.strip())
    for field, key, floor in _NUM_FIELDS:
        value = getattr(body, field)
        if value is not None:
            await settings.set(key, str(max(floor, value)))
    return await _read(settings)


@router.post("/refresh-locations", response_model=SiteSettingsOut)
async def refresh_site_locations(
    request: Request, session: DbSession, admin: AdminUser
) -> SiteSettingsOut:
    """Re-derive ``SITE_LOCATIONS`` from the site trial squad's remark NAMES (matched by name, never
    an index) — keeps the picker aligned with the panel after squad/host changes."""
    settings = _settings(request, session)
    squad = await settings.get(SiteSettingKey.SITE_TRIAL_SQUAD)
    if not squad:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "site trial squad not configured")
    try:
        names = await request.app.state.panel.squad_location_names(squad)
    except RemnawaveError as exc:
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, "panel unreachable") from exc
    if not names:
        # Persisting [] used to be silent and doubly wrong: the picker went empty for new visitors
        # while the claim-time filter read the same [] as "no filtering", letting every host
        # through. Refuse instead, and leave the last working list in place.
        raise HTTPException(
            status.HTTP_409_CONFLICT, "squad matched no enabled host — locations left unchanged"
        )
    await settings.set(SiteSettingKey.SITE_LOCATIONS, json.dumps(names))
    return await _read(settings)
