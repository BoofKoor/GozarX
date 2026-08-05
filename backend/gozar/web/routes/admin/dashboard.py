"""Dashboard (auth-gated): headline counts + activity/growth series + breakdowns + live panel stats.

DB counts reuse Phase 6 ``AdminService.stats()`` so the panel and the in-bot ``/admin`` never drift.
The chart series, language/location breakdowns, top referrers, growth and conversion are cheap
grouped queries over the same per-request session. The engagement + trial-health figures come from a
single ``GET /api/system/stats`` panel call (``online_now`` = the panel's live online count); if the
panel can't answer we fall back to the DB active-config count and zero the panel-only fields.
"""

from __future__ import annotations

import csv
import io
from dataclasses import asdict
from datetime import UTC, date, datetime, timedelta

from fastapi import APIRouter, Query, Request
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel

from gozar.db.repositories.config_log import ConfigLogRepository
from gozar.db.repositories.usage_sample import UsageSampleRepository
from gozar.db.repositories.user import UserRepository
from gozar.remnawave.schemas import SystemStats
from gozar.services.admin import AdminService
from gozar.services.settings_service import SettingKey, SettingsService, SiteSettingKey
from gozar.services.stats import (
    pct_change,
    previous_window,
    start_of_today,
    window_start,
    zero_filled_daily,
    zero_filled_daily_pairs,
)
from gozar.web.dependencies import AdminUser, DbSession

router = APIRouter(prefix="/dashboard", tags=["dashboard"])

_ALLOWED_RANGES = (7, 14, 30, 90)
_DEFAULT_RANGE = 14
_RETENTION_WEEKS = 8
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
    # window-over-window comparison — the SAME figures for the selected range and for the equally
    # long window immediately before it, so every headline KPI can carry an honest delta instead of
    # only the signups card. `*_delta_pct` is None when the prior window had no baseline.
    signups_in_range: int
    signups_prev_range: int
    signups_delta_pct: float | None
    claims_in_range: int
    claims_prev_range: int
    claims_delta_pct: float | None
    claimers_in_range: int
    claimers_prev_range: int
    claimers_delta_pct: float | None
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
    #: Users who signed up at or after the first referral was ever recorded — everyone who COULD
    #: have arrived via an invite. Not the whole user base: `referred_by` is NULL for every row the
    #: legacy import brought over, so dividing by all users measures how much of the service
    #: predates the referral programme rather than how well the programme works.
    eligible: int
    #: `joined / eligible`. The figure the dashboard's radar reads, so the axis can actually move.
    joined_share_pct: float


class SplitDayPoint(BaseModel):
    """One day of the new-vs-returning split. ``new`` counts users whose FIRST-EVER claim was that
    day; ``returning`` counts everyone else who claimed."""

    day: str
    new: int
    returning: int


class Metric(BaseModel):
    """A windowed figure next to the same figure over the previous, equal-length window.

    ``change_pct`` is ``None`` (not ``0.0``) when the baseline is zero or missing, so a first
    window reads as "new" rather than "flat" — the frontend renders the two cases differently.
    """

    value: float | None
    previous: float | None
    change_pct: float | None


class ReferralCap(BaseModel):
    limit: int  # the configured reward cap (0 = uncapped)
    at_cap: int  # inviters who have hit it and stopped earning
    with_referrals: int  # inviters with at least one successful invite


class DashboardAnalyticsOut(BaseModel):
    """Deeper analytics for the dashboard (separate from the cheap headline ``/stats`` so the top of
    the page stays fast). DAU/WAU/MAU are fixed 1/7/30-day active-claimer counts; activation, the
    referral funnel, the claim distribution and reminder split are all-time; the heatmaps, the
    active-user series and the new/returning split use the selected window."""

    range_days: int
    dau: int
    wau: int
    mau: int
    stickiness_pct: float  # dau / mau
    # Activation is WINDOWED: the cohort is everyone whose first claim landed in the selected
    # range, compared against the equally long window before it. It used to be an all-time figure
    # sitting under a range control that could not move it.
    median_hours_to_claim: Metric
    activation_24h: Metric  # share of the window's cohort that claimed within 24h of signing up
    first_claimers_in_range: int  # the cohort size both percentages are computed over
    claimers_all_time: int
    referral: ReferralFunnel
    referral_cap: ReferralCap
    heatmap: list[HeatCell]
    signup_heatmap: list[HeatCell]
    claims_distribution: dict[str, int]  # {"1","2-3","4-6","7+"} → users
    reminder_by_language: list[LangReminder]
    active_users_series: list[DayPoint]  # distinct claimers per day (DAU as a trend, not a point)
    new_vs_returning: list[SplitDayPoint]


class CohortRow(BaseModel):
    """One weekly signup cohort. ``retention[i]`` is the share (%) of the cohort that claimed in the
    i-th week after signup; index 0 is the signup week itself."""

    week: str  # ISO date of the cohort's Monday
    size: int
    retention: list[float]


class RetentionOut(BaseModel):
    weeks: int
    cohorts: list[CohortRow]


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
    new_today = await user_repo.count_created_since(start_of_today())
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

    # Window-over-window comparison. `previous_window` returns the equally long, non-overlapping
    # range immediately before the current one, so the deltas below compare like with like.
    prev_start, prev_end = previous_window(window)
    signups_in_range = await user_repo.count_created_since(since)
    signups_prev_range = await user_repo.count_created_between(prev_start, prev_end)
    claims_in_range = await config_log_repo.count_since(since)
    claims_prev_range = await config_log_repo.count_between(prev_start, prev_end)
    claimers_in_range = await config_log_repo.active_user_count_since(since)
    claimers_prev_range = await config_log_repo.active_user_count_between(prev_start, prev_end)

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
        signups_in_range=signups_in_range,
        signups_prev_range=signups_prev_range,
        signups_delta_pct=pct_change(signups_in_range, signups_prev_range),
        claims_in_range=claims_in_range,
        claims_prev_range=claims_prev_range,
        claims_delta_pct=pct_change(claims_in_range, claims_prev_range),
        claimers_in_range=claimers_in_range,
        claimers_prev_range=claimers_prev_range,
        claimers_delta_pct=pct_change(claimers_in_range, claimers_prev_range),
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
    request: Request,
    session: DbSession,
    admin: AdminUser,
    days: int = Query(default=_DEFAULT_RANGE),
) -> DashboardAnalyticsOut:
    window = days if days in _ALLOWED_RANGES else _DEFAULT_RANGE
    user_repo = UserRepository(session)
    log_repo = ConfigLogRepository(session)
    settings = SettingsService(session, request.app.state.redis)
    now = datetime.now(UTC)
    since = window_start(window)

    dau = await log_repo.active_user_count_since(now - timedelta(days=1))
    wau = await log_repo.active_user_count_since(now - timedelta(days=7))
    mau = await log_repo.active_user_count_since(now - timedelta(days=30))
    prev_since, prev_until = previous_window(window)
    median_h, within_24h, cohort = await log_repo.first_claim_stats(since=since)
    median_prev, within_prev, cohort_prev = await log_repo.first_claim_stats(
        since=prev_since, until=prev_until
    )
    _, _, claimers_all_time = await log_repo.first_claim_stats()
    joined, joined_claimed, referral_eligible = await user_repo.referral_funnel()
    total = await user_repo.count()
    referrals = await user_repo.sum_referrals()
    heatmap = await log_repo.hourly_weekday_counts(since)
    signup_heatmap = await user_repo.signups_hourly_weekday(since)
    distribution = await log_repo.claims_per_user_buckets()
    reminders = await user_repo.reminder_by_language()
    active_series = await log_repo.active_users_daily(since)
    split = await log_repo.new_vs_returning_daily(since)
    # The reward cap is a runtime setting — never hardcode the number (CLAUDE.md).
    cap = await settings.get_int(SettingKey.REFERRAL_REWARD_LIMIT, 0)
    at_cap, with_referrals = await user_repo.referral_cap_stats(cap)

    return DashboardAnalyticsOut(
        range_days=window,
        dau=dau,
        wau=wau,
        mau=mau,
        stickiness_pct=_pct(dau, mau),
        # Faster activation is an improvement, so the frontend has to know this metric's "good"
        # direction is DOWN. The sign convention stays the same as everywhere else; the label
        # carries the meaning.
        median_hours_to_claim=Metric(
            value=median_h,
            previous=median_prev,
            change_pct=pct_change(median_h, median_prev),
        ),
        activation_24h=Metric(
            value=_pct(within_24h, cohort),
            previous=_pct(within_prev, cohort_prev),
            change_pct=pct_change(_pct(within_24h, cohort), _pct(within_prev, cohort_prev)),
        ),
        first_claimers_in_range=cohort,
        claimers_all_time=claimers_all_time,
        referral=ReferralFunnel(
            joined=joined,
            joined_claimed=joined_claimed,
            invitee_conversion_pct=_pct(joined_claimed, joined),
            k_factor=round(referrals / total, 2) if total else 0.0,
            eligible=referral_eligible,
            joined_share_pct=_pct(joined, referral_eligible),
        ),
        referral_cap=ReferralCap(limit=cap, at_cap=at_cap, with_referrals=with_referrals),
        heatmap=[HeatCell(dow=d, hour=h, count=c) for d, h, c in heatmap],
        signup_heatmap=[HeatCell(dow=d, hour=h, count=c) for d, h, c in signup_heatmap],
        claims_distribution=distribution,
        reminder_by_language=[
            LangReminder(label=lang, on=on, off=off) for lang, on, off in reminders
        ],
        active_users_series=[
            DayPoint(day=d, count=n)
            for d, n in zero_filled_daily(active_series, since=since, days=window)
        ],
        new_vs_returning=[
            SplitDayPoint(day=d, new=a, returning=b)
            for d, a, b in zero_filled_daily_pairs(split, since=since, days=window)
        ],
    )


@router.get("/retention", response_model=RetentionOut)
async def dashboard_retention(
    session: DbSession,
    admin: AdminUser,
    weeks: int = Query(default=_RETENTION_WEEKS, ge=2, le=26),
) -> RetentionOut:
    """Weekly signup cohorts and how much of each came back to claim in later weeks.

    The one view that answers "do people stick?" — every other panel measures a single moment.
    Retention is returned as PERCENTAGES of the cohort so rows of different sizes are comparable;
    index 0 is the signup week itself (the activation rate), 1 the week after, and so on.
    """
    rows = await ConfigLogRepository(session).weekly_retention_cohorts(weeks)
    cohorts: list[CohortRow] = []
    today = datetime.now(UTC).date()
    for week, size, offsets in rows:
        # A row is as long as the weeks that have ELAPSED for that cohort, not as long as the weeks
        # somebody happened to come back in. Sized from the data, a cohort where nobody returned in
        # week two got a one-column row — indistinguishable from a cohort two days old whose week
        # two has not arrived — and the dashboard drops the short rows, so a 0% cohort was quietly
        # excluded from the average instead of counted as the zero it is. Elapsed weeks separate
        # "nobody came back" from "it has not happened yet", which are opposite facts.
        elapsed = (today - date.fromisoformat(week)).days // 7 + 1
        span = max(1, min(elapsed, weeks))
        cohorts.append(
            CohortRow(
                week=week,
                size=size,
                retention=[_pct(offsets.get(i, 0), size) for i in range(span)],
            )
        )
    return RetentionOut(weeks=weeks, cohorts=cohorts)


class UsageDay(BaseModel):
    """One LOCAL day of carried traffic and the concurrency during it."""

    day: str
    bytes: int
    peak_online: int
    avg_online: int
    #: The lifetime counter went DOWN across this day's boundary — a panel restart, a node removed
    #: and re-added, or a traffic reset. Traffic reads 0 for that day because the real figure is
    #: unknowable, and the flag is what lets the chart say so instead of drawing a silent dip.
    counter_reset: bool


class UsageOut(BaseModel):
    """The usage tab's whole payload.

    Separate from ``/stats`` and ``/analytics`` because it answers a different question — not who
    the users are, but what the service is carrying — and because it is the only figure set that
    did not exist before the sampler started running.
    """

    range_days: int
    #: When sampling began. ``None`` before the first sample. The frontend needs it to tell "no
    #: traffic in this window" apart from "we were not recording yet", which are different facts.
    recording_since: datetime | None
    samples: int
    #: Bytes carried in the window, against the same-length window before it.
    traffic: Metric
    #: Highest concurrent users seen in the window, against the previous window.
    peak_online: Metric
    #: Bytes per distinct claimer in the window — the average person's consumption.
    bytes_per_user: Metric
    nodes_online: int
    mem_used: int
    mem_total: int
    daily: list[UsageDay]


@router.get("/usage", response_model=UsageOut)
async def dashboard_usage(
    session: DbSession,
    admin: AdminUser,
    days: int = Query(default=_DEFAULT_RANGE),
) -> UsageOut:
    """Traffic and concurrency over time, from the hourly ``usage_samples`` recorder.

    Every figure here is WINDOWED with a previous-window twin, because the range control above the
    tab has to move all of them — a lifetime total sitting under a range picker is the exact thing
    the reporting conventions exist to prevent.
    """
    window = days if days in _ALLOWED_RANGES else _DEFAULT_RANGE
    since = window_start(window)
    prev_start, prev_end = previous_window(window)
    usage = UsageSampleRepository(session)
    logs = ConfigLogRepository(session)

    now = datetime.now(UTC)
    traffic = await usage.traffic_between(since, now)
    traffic_prev = await usage.traffic_between(prev_start, prev_end)
    peak = await usage.peak_online_between(since, now)
    peak_prev = await usage.peak_online_between(prev_start, prev_end)

    # Per-user consumption divides by the people who actually CLAIMED in the window, not by every
    # registered user: a signup who never took a config carried no bytes, and counting them would
    # make the average fall every time the bot gained a passer-by.
    claimers = await logs.active_user_count_since(since)
    claimers_prev = await logs.active_user_count_between(prev_start, prev_end)
    per_user = traffic / claimers if claimers else 0
    per_user_prev = traffic_prev / claimers_prev if claimers_prev else 0

    latest = await usage.latest()
    # The first day in the series has no predecessor to difference against, so its traffic is
    # structurally 0 — dropped rather than charted as a day the service sat idle.
    rows = await usage.daily(since.date())
    daily = [UsageDay(**asdict(r)) for r in rows[1:]] if len(rows) > 1 else []

    return UsageOut(
        range_days=window,
        recording_since=await usage.first_captured_at(),
        samples=await usage.sample_count(),
        traffic=Metric(
            value=float(traffic),
            previous=float(traffic_prev),
            change_pct=pct_change(traffic, traffic_prev),
        ),
        peak_online=Metric(
            value=float(peak), previous=float(peak_prev), change_pct=pct_change(peak, peak_prev)
        ),
        bytes_per_user=Metric(
            value=per_user,
            previous=per_user_prev,
            change_pct=pct_change(per_user, per_user_prev),
        ),
        nodes_online=latest.nodes_online if latest else 0,
        mem_used=latest.mem_used if latest else 0,
        mem_total=latest.mem_total if latest else 0,
        daily=daily,
    )


@router.get("/export.csv", response_class=PlainTextResponse)
async def dashboard_export(
    session: DbSession,
    admin: AdminUser,
    days: int = Query(default=_DEFAULT_RANGE),
) -> PlainTextResponse:
    """The window's daily series as CSV — signups, claims, distinct claimers, new vs returning.

    One file with every daily figure the dashboard charts, so the numbers can be checked or kept
    outside the panel. Written with ``csv`` rather than string joins so a location or label
    containing a comma can never shift the columns.
    """
    window = days if days in _ALLOWED_RANGES else _DEFAULT_RANGE
    since = window_start(window)
    user_repo = UserRepository(session)
    log_repo = ConfigLogRepository(session)

    signups = dict(
        zero_filled_daily(await user_repo.signups_daily(since), since=since, days=window)
    )
    claims = dict(zero_filled_daily(await log_repo.daily_counts(since), since=since, days=window))
    actives = dict(
        zero_filled_daily(await log_repo.active_users_daily(since), since=since, days=window)
    )
    split = {
        day: (new, returning)
        for day, new, returning in zero_filled_daily_pairs(
            await log_repo.new_vs_returning_daily(since), since=since, days=window
        )
    }

    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(
        ["day", "signups", "claims", "active_users", "new_claimers", "returning_claimers"]
    )
    for day in sorted(claims):
        new, returning = split.get(day, (0, 0))
        writer.writerow(
            [day, signups.get(day, 0), claims[day], actives.get(day, 0), new, returning]
        )

    return PlainTextResponse(
        buffer.getvalue(),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="gozar-dashboard-{window}d.csv"'},
    )
