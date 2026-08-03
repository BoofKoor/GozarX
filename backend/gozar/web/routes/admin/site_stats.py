"""Website funnel stats (auth-gated) — the identities→claims→active funnel + activity/locations.

Cheap grouped queries over the site tables (mirrors the bot dashboard's shape). No panel call is
needed; every number is local site data, so the endpoint never depends on Remnawave being reachable.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Query, Request
from pydantic import BaseModel

from gozar.db.repositories.push_subscription import PushSubscriptionRepository
from gozar.db.repositories.site_claim import SiteClaimRepository
from gozar.db.repositories.site_device import SiteDeviceRepository
from gozar.db.repositories.site_reward import SiteRewardRepository
from gozar.services.settings_service import SettingsService, SiteSettingKey
from gozar.services.stats import window_start, zero_filled_daily
from gozar.services.trial import start_of_today_utc
from gozar.web.dependencies import AdminUser, DbSession

router = APIRouter(prefix="/site/stats", tags=["site-stats"])

_ALLOWED_RANGES = (7, 14, 30, 90)
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


class RewardType(BaseModel):
    type: str
    grants: int
    total_mb: int


class PushHealth(BaseModel):
    active: int
    inactive: int
    by_locale: list[NamedCount]


class AbuseSignals(BaseModel):
    top_ip_buckets: list[NamedCount]  # buckets with >= 2 devices (soft farming signal)
    shared_fingerprint_devices: int


class SiteAnalyticsOut(BaseModel):
    """Deeper website analytics: active devices, the reward economy, streak reach, push-channel
    health, and soft anti-abuse signals. All local site data — never depends on the panel.

    ``range_days`` echoes the window the WINDOWED figures used, and ``all_time_note`` marks that the
    rest (reward totals, streak reach, push health, abuse signals) are lifetime figures. The page's
    7/14/30 buttons used to move only the funnel above this band while everything here silently
    ignored them — the control lied about half the screen.
    """

    range_days: int
    dau: int
    wau: int
    mau: int
    stickiness_pct: float
    claims_in_range: int
    devices_active_in_range: int
    reward_economy: list[RewardType]
    streak_distribution: dict[str, int]
    active_streaks: int
    push: PushHealth
    abuse: AbuseSignals


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


@router.get("/analytics", response_model=SiteAnalyticsOut)
async def site_analytics(
    request: Request,
    session: DbSession,
    admin: AdminUser,
    days: int = Query(default=_DEFAULT_RANGE),
) -> SiteAnalyticsOut:
    window = days if days in _ALLOWED_RANGES else _DEFAULT_RANGE
    devices = SiteDeviceRepository(session)
    claims = SiteClaimRepository(session)
    rewards = SiteRewardRepository(session)
    push = PushSubscriptionRepository(session)
    settings = SettingsService(session, request.app.state.redis)
    now = datetime.now(UTC)
    since = window_start(window)

    dau = await devices.active_since(now - timedelta(days=1))
    wau = await devices.active_since(now - timedelta(days=7))
    mau = await devices.active_since(now - timedelta(days=30))
    streak_days = await settings.get_int(SiteSettingKey.SITE_STREAK_DAYS, 0)
    active_streaks = await devices.active_streak_count(streak_days) if streak_days > 0 else 0
    active, inactive = await push.count_by_active()

    return SiteAnalyticsOut(
        range_days=window,
        claims_in_range=await claims.count_since(since),
        devices_active_in_range=await devices.active_since(since),
        dau=dau,
        wau=wau,
        mau=mau,
        stickiness_pct=_pct(dau, mau),
        reward_economy=[
            RewardType(type=t, grants=g, total_mb=mb) for t, g, mb in await rewards.totals_by_type()
        ],
        streak_distribution=await devices.streak_distribution(),
        active_streaks=active_streaks,
        push=PushHealth(
            active=active,
            inactive=inactive,
            by_locale=[NamedCount(label=loc, count=n) for loc, n in await push.locale_breakdown()],
        ),
        abuse=AbuseSignals(
            top_ip_buckets=[
                NamedCount(label=b, count=n) for b, n in await devices.top_ip_buckets()
            ],
            shared_fingerprint_devices=await devices.shared_fingerprint_device_count(),
        ),
    )
