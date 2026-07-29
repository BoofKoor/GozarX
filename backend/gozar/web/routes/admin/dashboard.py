"""Dashboard (auth-gated): headline counts + activity/growth series + breakdowns + live panel stats.

DB counts reuse Phase 6 ``AdminService.stats()`` so the panel and the in-bot ``/admin`` never drift.
The chart series, language/location breakdowns, top referrers, growth and conversion are cheap
grouped queries over the same per-request session. The engagement + trial-health figures come from a
single ``GET /api/system/stats`` panel call (``online_now`` = the panel's live online count); if the
panel can't answer we fall back to the DB active-config count and zero the panel-only fields.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Query, Request
from pydantic import BaseModel

from gozar.db.repositories.config_log import ConfigLogRepository
from gozar.db.repositories.user import UserRepository
from gozar.remnawave.schemas import SystemStats
from gozar.services.admin import AdminService
from gozar.services.settings_service import SettingKey, SettingsService, SiteSettingKey
from gozar.services.stats import window_start, zero_filled_daily
from gozar.services.trial import start_of_today_utc
from gozar.web.dependencies import AdminUser, DbSession

router = APIRouter(prefix="/dashboard", tags=["dashboard"])

_ALLOWED_RANGES = (7, 14, 30)
_DEFAULT_RANGE = 14
_SQUAD_ONLINE_KEY = "cache:squad_online"
_SQUAD_ONLINE_TTL = 60  # seconds — matches the panel's online cadence; caps the pagination cost


async def _online_now(
    panel: object,
    settings: SettingsService,
    redis: object,
    stats: SystemStats | None,
    db_active: int,
) -> tuple[int, bool]:
    """(online_now, squad_scoped). Prefer the count of trial-squad users online in the last minute
    (excludes the operator's personal squads that inflate the panel-wide figure); 60s-cached. Falls
    back to the panel-wide ``onlineNow`` (or the DB active count when the panel is down)."""
    panel_wide = stats.online_now if stats is not None else db_active
    squads = {
        s
        for s in (
            await settings.get(SettingKey.TRIAL_SQUAD),
            await settings.get(SiteSettingKey.SITE_TRIAL_SQUAD),
        )
        if s
    }
    if not squads:
        return panel_wide, False
    cached = await redis.get(_SQUAD_ONLINE_KEY)  # type: ignore[attr-defined]
    if cached is not None:
        return int(cached), True
    count = await panel.squad_online_count(squads)  # type: ignore[attr-defined]
    if count is None:
        return panel_wide, False
    await redis.set(_SQUAD_ONLINE_KEY, count, ex=_SQUAD_ONLINE_TTL)  # type: ignore[attr-defined]
    return count, True


class DayPoint(BaseModel):
    day: str
    count: int


class NamedCount(BaseModel):
    label: str
    count: int


class Referrer(BaseModel):
    telegram_id: int
    referral_count: int


class DashboardOut(BaseModel):
    # headline + DB status (Phase 6 stats)
    total_users: int
    available: int
    active: int
    banned: int
    configs_today: int
    referrals: int
    range_days: int
    # user growth (DB)
    new_today: int
    new_this_week: int
    growth_pct: float | None  # this week's signups vs last week's; None = no prior-week baseline
    # engagement (panel /system/stats)
    online_now: int
    online_squad_scoped: bool  # True: online_now counts only the trial squad(s); False: panel-wide
    online_last_day: int
    online_last_week: int
    never_online: int
    panel_online: bool  # whether the panel stats were reachable (frontend can dim panel-only cards)
    # trial health & traffic (panel)
    panel_status_counts: dict[str, int]
    panel_total_users: int
    total_traffic_bytes: int
    nodes_online: int
    # referral & conversion (DB)
    conversion_pct: float
    reminder_enabled: int
    avg_referrals: float
    # series + breakdowns
    claims_series: list[DayPoint]
    signups_series: list[DayPoint]
    languages: list[NamedCount]
    top_locations: list[NamedCount]
    top_referrers: list[Referrer]


class HeatCell(BaseModel):
    dow: int  # 0=Sunday .. 6=Saturday (Postgres), in Asia/Tehran local time
    hour: int
    count: int


class LangReminder(BaseModel):
    label: str
    on: int
    off: int


class ReferralFunnel(BaseModel):
    joined: int  # users who arrived via a referral link
    joined_claimed: int  # of those, how many ever claimed a config
    invitee_conversion_pct: float
    k_factor: float  # avg successful invites per user (viral coefficient); >1 ⇒ self-sustaining


class DashboardAnalyticsOut(BaseModel):
    """Deeper analytics for the dashboard (separate from the cheap headline ``/stats`` so the top of
    the page stays fast). DAU/WAU/MAU are fixed 1/7/30-day active-claimer counts; activation, the
    referral funnel, the claim distribution and reminder split are all-time; the heatmap uses the
    selected window."""

    range_days: int
    dau: int
    wau: int
    mau: int
    stickiness_pct: float  # dau / mau
    median_hours_to_claim: float | None
    activation_24h_pct: float  # share of claimers whose first claim was within 24h of signup
    claimers: int
    referral: ReferralFunnel
    heatmap: list[HeatCell]
    claims_distribution: dict[str, int]  # {"1","2-3","4-6","7+"} → users
    reminder_by_language: list[LangReminder]


def _pct(part: int, whole: int) -> float:
    return round(part / whole * 100, 1) if whole else 0.0


@router.get("/stats", response_model=DashboardOut)
async def dashboard_stats(
    request: Request,
    session: DbSession,
    admin: AdminUser,
    days: int = Query(default=_DEFAULT_RANGE),
) -> DashboardOut:
    window = days if days in _ALLOWED_RANGES else _DEFAULT_RANGE
    user_repo = UserRepository(session)
    config_log_repo = ConfigLogRepository(session)
    settings = SettingsService(session, request.app.state.redis)
    panel = request.app.state.panel
    admin_svc = AdminService(user_repo, config_log_repo, settings, panel, request.app.state.redis)
    s = await admin_svc.stats()

    now = datetime.now(UTC)
    # Inclusive N-calendar-day window anchored on a UTC day boundary, so the oldest bucket is
    # complete and the zero-filled series spans exactly `window` days (see services/stats.py).
    since = window_start(window)
    claims = await config_log_repo.daily_counts(since)
    signups = await user_repo.signups_daily(since)
    languages = await user_repo.language_breakdown()
    top_locations = await config_log_repo.location_counts(since)
    referrers = await user_repo.top_referrers()

    # User growth: today, this week, and week-over-week change (independent of the chart range).
    new_today = await user_repo.count_created_since(start_of_today_utc())
    new_this_week = await user_repo.count_created_since(now - timedelta(days=7))
    two_weeks = await user_repo.count_created_since(now - timedelta(days=14))
    prev_week = two_weeks - new_this_week
    # None (not 0.0) when there's no prior-week baseline, so a launch week with signups doesn't read
    # as "0% — flat". The frontend renders None as a "new" badge when this week has signups.
    growth_pct = round((new_this_week - prev_week) / prev_week * 100, 1) if prev_week else None

    # Referral & conversion.
    claimed = await config_log_repo.distinct_user_count()
    reminder_enabled = await user_repo.count_reminder_enabled()
    avg_referrals = round(s.referrals / s.total, 2) if s.total else 0.0

    # Engagement + trial health from one panel call (graceful when unreachable).
    stats = await panel.system_stats()
    # "Online now" scoped to the service's trial squad(s) — the panel-wide onlineNow also counts the
    # operator's OWN personal squads. Cached 60s (bounded pagination is heavy). Falls back to the
    # panel-wide figure when no squad is configured or the scoped call fails.
    online_now, online_squad_scoped = await _online_now(
        panel, settings, request.app.state.redis, stats, s.active
    )

    return DashboardOut(
        total_users=s.total,
        available=s.available,
        active=s.active,
        banned=s.banned,
        configs_today=s.configs_today,
        referrals=s.referrals,
        range_days=window,
        new_today=new_today,
        new_this_week=new_this_week,
        growth_pct=growth_pct,
        online_now=online_now,
        online_squad_scoped=online_squad_scoped,
        online_last_day=stats.online_last_day if stats else 0,
        online_last_week=stats.online_last_week if stats else 0,
        never_online=stats.never_online if stats else 0,
        panel_online=stats is not None,
        panel_status_counts=stats.status_counts if stats else {},
        panel_total_users=stats.total_users if stats else 0,
        total_traffic_bytes=stats.total_traffic_bytes if stats else 0,
        nodes_online=stats.nodes_online if stats else 0,
        conversion_pct=_pct(claimed, s.total),
        reminder_enabled=reminder_enabled,
        avg_referrals=avg_referrals,
        claims_series=[
            DayPoint(day=d, count=n) for d, n in zero_filled_daily(claims, since=since, days=window)
        ],
        signups_series=[
            DayPoint(day=d, count=n)
            for d, n in zero_filled_daily(signups, since=since, days=window)
        ],
        languages=[NamedCount(label=lang, count=n) for lang, n in languages],
        top_locations=[NamedCount(label=loc, count=n) for loc, n in top_locations],
        top_referrers=[Referrer(telegram_id=t, referral_count=n) for t, n in referrers],
    )


@router.get("/analytics", response_model=DashboardAnalyticsOut)
async def dashboard_analytics(
    session: DbSession,
    admin: AdminUser,
    days: int = Query(default=_DEFAULT_RANGE),
) -> DashboardAnalyticsOut:
    window = days if days in _ALLOWED_RANGES else _DEFAULT_RANGE
    user_repo = UserRepository(session)
    log_repo = ConfigLogRepository(session)
    now = datetime.now(UTC)

    dau = await log_repo.active_user_count_since(now - timedelta(days=1))
    wau = await log_repo.active_user_count_since(now - timedelta(days=7))
    mau = await log_repo.active_user_count_since(now - timedelta(days=30))
    median_h, within_24h, claimers = await log_repo.first_claim_stats()
    joined, joined_claimed = await user_repo.referral_funnel()
    total = await user_repo.count()
    referrals = await user_repo.sum_referrals()
    heatmap = await log_repo.hourly_weekday_counts(window_start(window))
    distribution = await log_repo.claims_per_user_buckets()
    reminders = await user_repo.reminder_by_language()

    return DashboardAnalyticsOut(
        range_days=window,
        dau=dau,
        wau=wau,
        mau=mau,
        stickiness_pct=_pct(dau, mau),
        median_hours_to_claim=median_h,
        activation_24h_pct=_pct(within_24h, claimers),
        claimers=claimers,
        referral=ReferralFunnel(
            joined=joined,
            joined_claimed=joined_claimed,
            invitee_conversion_pct=_pct(joined_claimed, joined),
            k_factor=round(referrals / total, 2) if total else 0.0,
        ),
        heatmap=[HeatCell(dow=d, hour=h, count=c) for d, h, c in heatmap],
        claims_distribution=distribution,
        reminder_by_language=[
            LangReminder(label=lang, on=on, off=off) for lang, on, off in reminders
        ],
    )
