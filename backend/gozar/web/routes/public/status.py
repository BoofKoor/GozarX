"""Public read-only endpoints: device status + public runtime config.

``GET /status`` resolves (or mints) the caller's device and reports its state from the
``site_devices`` row alone — no panel call yet (the live quota/traffic view is fleshed out in P4).
``GET /config`` hands the SPA the public keys it needs at runtime (CLAUDE.md 'runtime config').
"""

from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel

from gozar.config.settings import get_settings
from gozar.db.models.site_device import SiteDeviceStatus
from gozar.web.routes.public.identity import CurrentDevice

router = APIRouter(tags=["public"])


class DeviceStatus(BaseModel):
    status: str
    has_config: bool
    referral_count: int
    streak_count: int


class PublicConfig(BaseModel):
    turnstile_site_key: str
    vapid_public_key: str
    turnstile_enabled: bool


@router.get("/status", response_model=DeviceStatus)
async def get_status(device: CurrentDevice) -> DeviceStatus:
    return DeviceStatus(
        status=device.status,
        has_config=device.status == SiteDeviceStatus.active_config,
        referral_count=device.referral_count,
        streak_count=device.streak_count,
    )


@router.get("/config", response_model=PublicConfig)
async def get_config() -> PublicConfig:
    settings = get_settings()
    return PublicConfig(
        turnstile_site_key=settings.turnstile_site_key,
        vapid_public_key=settings.vapid_public_key,
        turnstile_enabled=bool(settings.turnstile_secret.get_secret_value()),
    )
