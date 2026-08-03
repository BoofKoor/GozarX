"""Website funnel stats (auth-gated) — the visitors→claimers→active funnel + activity/locations.

Cheap grouped queries over the site tables (mirrors the bot dashboard's shape). No panel call is
needed; every number is local site data, so the endpoint never depends on Remnawave being reachable.

**What this endpoint used to get wrong**, and what changed:

* *"Visits" counted identities, forever.* The headline was ``site_devices.count()`` — every identity
  ever minted. Because ``/status`` resolves a device on every page load, a client that refuses
  cookies mints a fresh row per request, so the number drifted up on its own and dragged
  ``conversion_pct`` down with it. Visitors are now measured from ``last_seen_at`` inside the
  selected window; the lifetime figure is still reported, but explicitly named ``*_all_time``.
* *No range applied to the KPI row.* A 7/14/30/90 control sat above numbers that were all-time or
  today-only, so changing it moved nothing. Every KPI here is now windowed, with the previous,
  equal-length window alongside it for an honest delta.
* *"Today" was a UTC day.* The operator reads these on Iran time, so for the first 3.5 hours of
  every local day "دریافت امروز" showed yesterday's total. ``services.stats.start_of_today``
  anchors on the local day (display only — the claim cooldown is a rolling window, untouched).
* *Active configs trusted a status column.* ``status`` is healed by the panel webhook or the
  15-minute reconcile sweep, and the sweep skips a device whenever the panel is unreachable — so
  during an outage dead trials kept counting as active. It is now split into live vs stale.
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
from gozar.services.site_trial import _DEFAULT_SITE_TRIAL_HOURS
from gozar.services.stats import (
    pct_change,
    previous_window,
    start_of_today,
    window_start,
    zero_filled_daily,
)
from gozar.web.dependencies import AdminUser, DbSession

router = APIRouter(prefix="/site/stats", tags=["site-stats"])

_ALLOWED_RANGES = (7, 14, 30, 90)
_DEFAULT_RANGE = 14
_TOP_LOCATIONS = 10


class DayPoint(BaseModel):
    day: str
    count: int


class NamedCount(BaseModel):
    label: str
    count: int


class Metric(BaseModel):
    """A windowed figure next to the same figure over the previous, equal-length window.

    ``change_pct`` is ``None`` (not ``0.0``) when the baseline is zero, so a launch week reads as
    "new" instead of "flat" — the frontend renders the two cases differently.
    """

    value: int
    previous: int
    change_pct: float | None


class SiteStatsOut(BaseModel):
    """The site funnel for the selected window, plus the lifetime figures it sits inside.

    Everything named ``*_all_time`` is deliberately outside the range control; everything else moves
    with it. Mixing the two silently — which is what this endpoint used to do — is what made the
    range buttons look broken.
    """

    range_days: int

    # --- windowed funnel ---
    visitors: Metric  # devices seen in the window (last_seen_at)
    new_visitors: Metric  # devices whose identity was minted in the window
    returning_visitors: Metric  # seen in the window, minted before it
    claimers: Metric  # distinct devices that provisioned in the window
    claims: Metric  # provisions in the window (change-location re-picks excluded)
    conversion_pct: float  # claimers / visitors, both windowed
    conversion_pct_prev: float
    location_changes: int  # change-location re-picks — excluded everywhere else

    # --- lifetime ---
    total_devices_all_time: int
    devices_claimed_all_time: int
    conversion_all_time_pct: float

    # --- right now ---
    active_configs_live: int  # trial window hasn't elapsed
    active_configs_stale: int  # status still active_config, trial window already over
    push_subscribers: int
    configs_today: int  # local (Asia/Tehran) day, not UTC
    status_counts: dict[str, int]

    # --- series + breakdown ---
    claims_series: list[DayPoint]
    visitors_series: list[DayPoint]
    top_locations: list[NamedCount]
    locations_total: int  # distinct locations claimed in the window (top_locations is capped)


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

    ``range_days`` echoes the window the WINDOWED figures used; the reward totals, streak reach,
    push health and abuse signals are lifetime figures and are labelled as such in the UI.

    The DAU/WAU/MAU trio is deliberately reported twice over: ``dau``/``wau``/``mau`` count devices
    that PROVISIONED (the conversion-side signal, which is what the numbers always were), and
    ``visitors_*`` count devices that were SEEN. Before ``last_seen_at`` existed the site had no
    visit signal at all, so "active users" could only ever mean "claimed something" — which
    undercounts everyone who came back, read the page, and didn't claim.
    """

    range_days: int
    dau: int
    wau: int
    mau: int
    stickiness_pct: float
    visitors_24h: int
    visitors_7d: int
    visitors_30d: int
    visit_stickiness_pct: float
    claims_in_range: int
    devices_active_in_range: int
    reward_economy: list[RewardType]
    streak_distribution: dict[str, int]
    active_streaks: int
    push: PushHealth
    abuse: AbuseSignals


def _pct(part: int, whole: int) -> float:
    return round(part / whole * 100, 1) if whole else 0.0


def _metric(value: int, previous: int) -> Metric:
    return Metric(value=value, previous=previous, change_pct=pct_change(value, previous))


@router.get("/", response_model=SiteStatsOut)
async def site_stats(
    request: Request,
    session: DbSession,
    admin: AdminUser,
    days: int = Query(default=_DEFAULT_RANGE),
) -> SiteStatsOut:
    window = days if days in _ALLOWED_RANGES else _DEFAULT_RANGE
    devices = SiteDeviceRepository(session)
    claims = SiteClaimRepository(session)
    push = PushSubscriptionRepository(session)
    settings = SettingsService(session, request.app.state.redis)

    # Inclusive N-local-calendar-day window; the series is zero-filled (services/stats). ``now`` is
    # the current window's exclusive upper bound so it lines up with the previous window's `[a, b)`.
    since = window_start(window)
    now = datetime.now(UTC)
    prev_start, prev_end = previous_window(window)

    visitors = await devices.count_seen_between(since, now)
    visitors_prev = await devices.count_seen_between(prev_start, prev_end)
    claimers = await claims.distinct_device_count_between(since, now)
    claimers_prev = await claims.distinct_device_count_between(prev_start, prev_end)

    status_counts = await devices.count_by_status()
    trial_hours = await settings.get_int(SiteSettingKey.SITE_TRIAL_HOURS, _DEFAULT_SITE_TRIAL_HOURS)
    live, stale = await devices.active_config_split(trial_hours)

    total_devices = await devices.count()
    devices_claimed = await claims.distinct_device_count()
    daily = await claims.daily_counts(since)
    seen = await devices.seen_daily(since)
    top_locations = await claims.location_counts(since, limit=_TOP_LOCATIONS)

    return SiteStatsOut(
        range_days=window,
        visitors=_metric(visitors, visitors_prev),
        new_visitors=_metric(
            await devices.count_new_between(since, now),
            await devices.count_new_between(prev_start, prev_end),
        ),
        returning_visitors=_metric(
            await devices.count_returning_between(since, now),
            await devices.count_returning_between(prev_start, prev_end),
        ),
        claimers=_metric(claimers, claimers_prev),
        claims=_metric(
            await claims.count_since(since), await claims.count_between(prev_start, prev_end)
        ),
        conversion_pct=_pct(claimers, visitors),
        conversion_pct_prev=_pct(claimers_prev, visitors_prev),
        location_changes=await claims.change_count_since(since),
        total_devices_all_time=total_devices,
        devices_claimed_all_time=devices_claimed,
        conversion_all_time_pct=_pct(devices_claimed, total_devices),
        active_configs_live=live,
        active_configs_stale=stale,
        push_subscribers=await push.count_active(),
        configs_today=await claims.count_since(start_of_today()),
        status_counts=status_counts,
        claims_series=[
            DayPoint(day=d, count=n) for d, n in zero_filled_daily(daily, since=since, days=window)
        ],
        visitors_series=[
            DayPoint(day=d, count=n) for d, n in zero_filled_daily(seen, since=since, days=window)
        ],
        top_locations=[NamedCount(label=loc, count=n) for loc, n in top_locations],
        locations_total=await claims.location_total(since),
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
    seen_1 = await devices.count_seen_between(now - timedelta(days=1), now)
    seen_7 = await devices.count_seen_between(now - timedelta(days=7), now)
    seen_30 = await devices.count_seen_between(now - timedelta(days=30), now)
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
        visitors_24h=seen_1,
        visitors_7d=seen_7,
        visitors_30d=seen_30,
        visit_stickiness_pct=_pct(seen_1, seen_30),
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
