"""Website funnel stats (auth-gated) — the identities→claims→active funnel + activity/locations.

Cheap grouped queries over the site tables (mirrors the bot dashboard's shape). No panel call is
needed; every number is local site data, so the endpoint never depends on Remnawave being reachable.
"""

from __future__ import annotations

from fastapi import APIRouter, Query
from pydantic import BaseModel

from gozar.db.repositories.push_subscription import PushSubscriptionRepository
from gozar.db.repositories.site_claim import SiteClaimRepository
from gozar.db.repositories.site_device import SiteDeviceRepository
from gozar.services.stats import window_start, zero_filled_daily
from gozar.services.trial import start_of_today_utc
from gozar.web.dependencies import AdminUser, DbSession

router = APIRouter(prefix="/site/stats", tags=["site-stats"])

_ALLOWED_RANGES = (7, 14, 30)
_DEFAULT_RANGE = 14


class DayPoint(BaseModel):
    day: str
    count: int


class NamedCount(BaseModel):
    label: str
    count: int


class SiteStatsOut(BaseModel):
    total_devices: int  # identities minted ("visits")
    devices_claimed: int  # distinct devices that claimed ≥1 config
    active_configs: int  # devices holding a live config right now
    conversion_pct: float  # devices_claimed / total_devices
    configs_today: int
    push_subscribers: int
    range_days: int
    status_counts: dict[str, int]
    claims_series: list[DayPoint]
    top_locations: list[NamedCount]


def _pct(part: int, whole: int) -> float:
    return round(part / whole * 100, 1) if whole else 0.0


@router.get("/", response_model=SiteStatsOut)
async def site_stats(
    session: DbSession,
    admin: AdminUser,
    days: int = Query(default=_DEFAULT_RANGE),
) -> SiteStatsOut:
    window = days if days in _ALLOWED_RANGES else _DEFAULT_RANGE
    devices = SiteDeviceRepository(session)
    claims = SiteClaimRepository(session)
    push = PushSubscriptionRepository(session)

    # Inclusive N-calendar-day window on a UTC day boundary; series is zero-filled (services/stats).
    since = window_start(window)
    total_devices = await devices.count()
    status_counts = await devices.count_by_status()
    devices_claimed = await claims.distinct_device_count()
    daily = await claims.daily_counts(since)
    top_locations = await claims.location_counts(since)

    return SiteStatsOut(
        total_devices=total_devices,
        devices_claimed=devices_claimed,
        active_configs=status_counts.get("active_config", 0),
        conversion_pct=_pct(devices_claimed, total_devices),
        configs_today=await claims.count_since(start_of_today_utc()),
        push_subscribers=await push.count_active(),
        range_days=window,
        status_counts=status_counts,
        claims_series=[
            DayPoint(day=d, count=n) for d, n in zero_filled_daily(daily, since=since, days=window)
        ],
        top_locations=[NamedCount(label=loc, count=n) for loc, n in top_locations],
    )
