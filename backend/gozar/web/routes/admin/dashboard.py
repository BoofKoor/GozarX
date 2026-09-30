"""Dashboard (auth-gated): headline counts + activity/growth series + breakdowns + live panel stats.

The headline is DATABASE-first: a handful of grouped queries over the per-request session. The
engagement + trial-health figures come from the panel's ``/system/stats``, read through
``services.panel_cache`` (one bounded call, shared and briefly cached) and fetched BEFORE the first
query, so no pooled connection sits idle while the panel answers.

"Online now" is scoped to the trial squad(s). Counting it means paging through every panel user, so
it is never done here: the worker records it (``refresh_squad_online``) and this route reads the
last recorded figure, asking for a fresh one when it is stale. Until one exists the panel-wide count
stands in, flagged by ``online_squad_scoped = False``. Either way ``online_week`` comes from the
SAME population, since the overview gauges one against the other.

A panel figure the panel did not give is ``None``, never ``0``: "the panel carried 0 B" and "the
panel did not answer" are opposite facts, and the old zeros drew the second as the first.
"""

from __future__ import annotations

import csv
import io
from dataclasses import asdict
from datetime import UTC, date, datetime, timedelta

from fastapi import APIRouter, Query, Request
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel

from gozar.config.reporting import DISPLAY_TZ
from gozar.db.repositories.config_log import ConfigLogRepository
from gozar.db.repositories.site_claim import SiteClaimRepository
from gozar.db.repositories.usage_sample import UsageSampleRepository
from gozar.db.repositories.user import UserRepository
from gozar.remnawave.schemas import SystemStats
from gozar.services.panel_cache import (
    SQUAD_ONLINE_FRESH,
    read_squad_online,
    read_system_stats,
    request_squad_online_refresh,
)
from gozar.services.settings_service import SettingKey, SettingsService, SiteSettingKey
from gozar.services.stats import (
    pct_change,
    previous_window,
    start_of_today,
    window_start,
    zero_filled_daily,
    zero_filled_daily_pairs,
)
from gozar.services.trial import _DEFAULT_TRIAL_HOURS
from gozar.web.dependencies import AdminUser, DbSession

router = APIRouter(prefix="/dashboard", tags=["dashboard"])

_ALLOWED_RANGES = (7, 14, 30, 90)
_DEFAULT_RANGE = 14
_RETENTION_WEEKS = 8
#: The deeper analytics are ~20 aggregates over every claim ever made and are polled by every open
#: dashboard tab; a minute of staleness is invisible at that cadence and saves each tab the scans.
_ANALYTICS_TTL = 60
_RETENTION_TTL = 300


def _analytics_key(window: int) -> str:
    return f"cache:dash:analytics:{window}"


def _retention_key(weeks: int) -> str:
    return f"cache:dash:retention:{weeks}"


async def _online_now(
    request: Request, settings: SettingsService, stats: SystemStats | None
) -> tuple[int | None, int | None, bool]:
    """``(online_now, online_week, squad_scoped)``: the last recorded trial-squad figures when they
    exist, else the panel-wide pair — never one of each, since the gauge divides one by the other.
    ``None`` when neither is known. Never pages the panel itself — see the module docstring."""
    panel_now = stats.online_now if stats is not None else None
    panel_week = stats.online_last_week if stats is not None else None
    squads = {
        s
        for s in (
            await settings.get(SettingKey.TRIAL_SQUAD),
            await settings.get(SiteSettingKey.SITE_TRIAL_SQUAD),
        )
        if s
    }
    if not squads:
        return panel_now, panel_week, False
    recorded = await read_squad_online(request.app.state.redis)
    if recorded is None or recorded.age > SQUAD_ONLINE_FRESH:
        await request_squad_online_refresh(getattr(request.app.state, "arq", None))
    if recorded is None:
        return panel_now, panel_week, False
    return recorded.count, recorded.week, True


class DayPoint(BaseModel):
    day: str
    count: int


class NamedCount(BaseModel):
    label: str
    count: int


class Referrer(BaseModel):
    telegram_id: int
    referral_count: int


class Metric(BaseModel):
    """A windowed figure next to the same figure over the previous, equal-length window.

    ``change_pct`` is ``None`` (not ``0.0``) when the baseline is zero or missing, so a first
    window reads as "new" rather than "flat" — the frontend renders the two cases differently.
    """

    value: float | None
    previous: float | None
    change_pct: float | None


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
    #: ``active`` split by whether the trial window has actually elapsed. The status is healed only
    #: by the panel webhook or the reconcile sweep, which skips users while the panel is down, so
    #: the raw count overstates what is running (see ``UserRepository.active_config_split``).
    active_live: int
    active_stale: int
    # engagement (panel /system/stats). ``None`` wherever the panel did not answer.
    online_now: int | None
    online_squad_scoped: bool  # True: online_now counts only the trial squad(s); False: panel-wide
    #: Seen online in the last 7 days, in the SAME population as ``online_now`` — the gauge's
    #: denominator. The panel-wide week figure stays in ``online_last_week``.
    online_week: int | None
    online_last_day: int | None
    online_last_week: int | None
    never_online: int | None
    panel_online: bool  # whether the panel stats were reachable (frontend can dim panel-only cards)
    # trial health & traffic (panel)
    panel_status_counts: dict[str, int]
    panel_total_users: int | None
    #: ``None`` when the panel is down OR answered without a usable traffic counter.
    total_traffic_bytes: int | None
    nodes_online: int | None
    # referral & conversion (DB)
    #: Of the users who signed up in the window, the share who have claimed — WINDOWED, with the
    #: previous window's twin, because it sits on the radar beside three windowed rates.
    conversion: Metric
    #: Every claimer ever over every user ever. Lifetime, and named so.
    conversion_pct_all_time: float
    reminder_enabled: int
    avg_referrals: float
    # series + breakdowns
    claims_series: list[DayPoint]
    signups_series: list[DayPoint]
    languages: list[NamedCount]  # lifetime: every user's current language
    top_locations: list[NamedCount]  # windowed, capped at ten
    #: Distinct locations claimed in the window — what the ten-row list above leaves out.
    locations_total: int
    top_referrers: list[Referrer]  # lifetime: referral_count is a running total


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


class ReferralCap(BaseModel):
    limit: int  # the configured reward cap (0 = NO invite is rewarded: min(referrals, cap))
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


def _pct_or_none(part: int, whole: int) -> float | None:
    """A share of an EMPTY group is unknown, not 0%: an empty cohort's activation read as 0% and,
    against a previous window that had one, as a 100% fall out of nothing."""
    return round(part / whole * 100, 1) if whole else None


@router.get("/stats", response_model=DashboardOut)
async def dashboard_stats(
    request: Request,
    session: DbSession,
    admin: AdminUser,
    days: int = Query(default=_DEFAULT_RANGE),
) -> DashboardOut:
    window = days if days in _ALLOWED_RANGES else _DEFAULT_RANGE
    redis = request.app.state.redis
    # The panel reading FIRST: the session has not touched the database yet, so no pooled
    # connection is held while the panel answers (it is usually a cache hit anyway).
    stats = (await read_system_stats(request.app.state.panel, redis)).stats

    user_repo = UserRepository(session)
    config_log_repo = ConfigLogRepository(session)
    settings = SettingsService(session, redis)

    now = datetime.now(UTC)
    # Inclusive N-calendar-day window anchored on a local day boundary, so the oldest bucket is
    # complete and the zero-filled series spans exactly `window` days (see services/stats.py).
    since = window_start(window)
    prev_start, prev_end = previous_window(window)
    today = start_of_today()

    # One pass over each table for every headline count (they were ~20 separate statements).
    users = await user_repo.summary(
        new_today=today,
        new_this_week=now - timedelta(days=7),
        new_two_weeks=now - timedelta(days=14),
        signups_in_range=since,
        signups_prev_range=(prev_start, prev_end),
    )
    logs = await config_log_repo.window_counts(
        today_start=today, since=since, prev_start=prev_start, prev_end=prev_end
    )
    claims = await config_log_repo.daily_counts(since)
    signups = await user_repo.signups_daily(since)
    languages = await user_repo.language_breakdown()
    top_locations = await config_log_repo.location_counts(since)
    locations_total = await config_log_repo.location_total(since)
    referrers = await user_repo.top_referrers()
    conversion = await user_repo.signup_conversion(range=(since, None), prev=(prev_start, prev_end))
    trial_hours = await settings.get_int(SettingKey.TRIAL_HOURS, _DEFAULT_TRIAL_HOURS)
    active_live, active_stale = await user_repo.active_config_split(trial_hours, now=now)

    total = users["total"]
    new_this_week = users["new_this_week"]
    prev_week = users["new_two_weeks"] - new_this_week
    # None (not 0.0) when there's no prior-week baseline, so a launch week with signups doesn't read
    # as "0% — flat". The frontend renders None as a "new" badge when this week has signups.
    growth_pct = round((new_this_week - prev_week) / prev_week * 100, 1) if prev_week else None
    avg_referrals = round(users["referrals"] / total, 2) if total else 0.0

    # "Online now" scoped to the service's trial squad(s) — the panel-wide onlineNow also counts the
    # operator's OWN personal squads. Read from what the worker recorded; see `_online_now`. With
    # the panel down and nothing recorded it is unknown — it used to fall back to the DATABASE's
    # active-config count, which is a different quantity drawn under the same label.
    online_now, online_week, online_squad_scoped = await _online_now(request, settings, stats)
    signed_up, converted = conversion["range"]
    signed_up_prev, converted_prev = conversion["prev"]
    conv_now = _pct_or_none(converted, signed_up)
    conv_prev = _pct_or_none(converted_prev, signed_up_prev)

    return DashboardOut(
        total_users=total,
        available=users["available"],
        active=users["active"],
        banned=users["banned"],
        configs_today=logs["claims_today"],
        referrals=users["referrals"],
        range_days=window,
        new_today=users["new_today"],
        new_this_week=new_this_week,
        growth_pct=growth_pct,
        signups_in_range=users["signups_in_range"],
        signups_prev_range=users["signups_prev_range"],
        signups_delta_pct=pct_change(users["signups_in_range"], users["signups_prev_range"]),
        claims_in_range=logs["claims_in_range"],
        claims_prev_range=logs["claims_prev_range"],
        claims_delta_pct=pct_change(logs["claims_in_range"], logs["claims_prev_range"]),
        claimers_in_range=logs["claimers_in_range"],
        claimers_prev_range=logs["claimers_prev_range"],
        claimers_delta_pct=pct_change(logs["claimers_in_range"], logs["claimers_prev_range"]),
        active_live=active_live,
        active_stale=active_stale,
        online_now=online_now,
        online_squad_scoped=online_squad_scoped,
        online_week=online_week,
        online_last_day=stats.online_last_day if stats else None,
        online_last_week=stats.online_last_week if stats else None,
        never_online=stats.never_online if stats else None,
        panel_online=stats is not None,
        panel_status_counts=stats.status_counts if stats else {},
        panel_total_users=stats.total_users if stats else None,
        total_traffic_bytes=(
            stats.total_traffic_bytes if stats is not None and stats.traffic_known else None
        ),
        nodes_online=stats.nodes_online if stats else None,
        conversion=Metric(
            value=conv_now, previous=conv_prev, change_pct=pct_change(conv_now, conv_prev)
        ),
        conversion_pct_all_time=_pct(logs["claimers_all_time"], total),
        reminder_enabled=users["reminder_enabled"],
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
        locations_total=locations_total,
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
    redis = request.app.state.redis
    cached = await redis.get(_analytics_key(window))
    if cached is not None:
        try:
            return DashboardAnalyticsOut.model_validate_json(cached)
        except ValueError:
            pass  # an unreadable entry is recomputed below
    out = await _compute_analytics(session, redis, window)
    await redis.set(_analytics_key(window), out.model_dump_json(), ex=_ANALYTICS_TTL)
    return out


async def _compute_analytics(session: object, redis: object, window: int) -> DashboardAnalyticsOut:
    user_repo = UserRepository(session)  # type: ignore[arg-type]
    log_repo = ConfigLogRepository(session)  # type: ignore[arg-type]
    settings = SettingsService(session, redis)  # type: ignore[arg-type]
    now = datetime.now(UTC)
    since = window_start(window)
    prev_since, prev_until = previous_window(window)

    actives = await log_repo.active_user_counts(
        dau=now - timedelta(days=1), wau=now - timedelta(days=7), mau=now - timedelta(days=30)
    )
    dau, wau, mau = actives["dau"], actives["wau"], actives["mau"]
    # Every user's first claim is derived ONCE for all three cohorts (it was three full passes).
    firsts = await log_repo.first_claim_windows(
        {"range": (since, None), "prev": (prev_since, prev_until), "all": (None, None)}
    )
    median_h, within_24h, cohort = firsts["range"]
    median_prev, within_prev, cohort_prev = firsts["prev"]
    claimers_all_time = firsts["all"][2]
    joined, joined_claimed, referral_eligible = await user_repo.referral_funnel()
    users = await user_repo.summary()
    total, referrals = users["total"], users["referrals"]
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
            value=_pct_or_none(within_24h, cohort),
            previous=_pct_or_none(within_prev, cohort_prev),
            change_pct=pct_change(
                _pct_or_none(within_24h, cohort), _pct_or_none(within_prev, cohort_prev)
            ),
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
    request: Request,
    session: DbSession,
    admin: AdminUser,
    weeks: int = Query(default=_RETENTION_WEEKS, ge=2, le=26),
) -> RetentionOut:
    """Weekly signup cohorts and how much of each came back to claim in later weeks.

    The one view that answers "do people stick?" — every other panel measures a single moment.
    Retention is returned as PERCENTAGES of the cohort so rows of different sizes are comparable;
    index 0 is the signup week itself (the activation rate), 1 the week after, and so on.
    """
    redis = request.app.state.redis
    cached = await redis.get(_retention_key(weeks))
    if cached is not None:
        try:
            return RetentionOut.model_validate_json(cached)
        except ValueError:
            pass
    rows = await ConfigLogRepository(session).weekly_retention_cohorts(weeks)
    cohorts: list[CohortRow] = []
    # The LOCAL date: cohorts are local weeks, and a UTC "today" is still yesterday until 03:30.
    today = datetime.now(DISPLAY_TZ).date()
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
    out = RetentionOut(weeks=weeks, cohorts=cohorts)
    await redis.set(_retention_key(weeks), out.model_dump_json(), ex=_RETENTION_TTL)
    return out


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
    #: Bytes carried in the window, against the same-length window before it. The panel's
    #: figure — everything it serves, the site and the operator's own squads included.
    traffic: Metric
    #: The panel's counter went DOWN inside the window, so ``traffic`` is a floor: what crossed the
    #: reset itself cannot be known.
    traffic_counter_reset: bool = False
    #: Highest concurrent users seen in the window, against the previous window.
    peak_online: Metric
    #: Panel traffic per distinct claimer in the window (bot + site). An upper bound on the average
    #: person's consumption, since the panel also carries the operator's own squads.
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
    window_traffic = await usage.traffic_between(since, now)
    traffic = window_traffic.bytes
    traffic_prev = (await usage.traffic_between(prev_start, prev_end)).bytes
    peak = await usage.peak_online_between(since, now)
    peak_prev = await usage.peak_online_between(prev_start, prev_end)

    # Per-user consumption divides by the people who actually CLAIMED in the window, not by every
    # registered user: a signup who never took a config carried no bytes. The panel reports ONE
    # traffic figure for everything it serves, so the claimers are the bot's AND the site's — the
    # bot's alone put the site's traffic on the bot's users. It is still an upper bound (the panel
    # also carries the operator's own squads), and the tab says so.
    site_claims = SiteClaimRepository(session)
    claimers = await logs.active_user_count_since(
        since
    ) + await site_claims.distinct_device_count_between(since, now)
    claimers_prev = await logs.active_user_count_between(
        prev_start, prev_end
    ) + await site_claims.distinct_device_count_between(prev_start, prev_end)
    per_user = traffic / claimers if claimers else 0
    per_user_prev = traffic_prev / claimers_prev if claimers_prev else 0

    latest = await usage.latest()
    # LOCAL days from the window's first. A partial first day (recording began inside the range)
    # is left out by the repository rather than charted as a day the service sat idle.
    rows = await usage.daily(since.astimezone(DISPLAY_TZ).date())
    daily = [UsageDay(**asdict(r)) for r in rows]

    return UsageOut(
        range_days=window,
        recording_since=await usage.first_captured_at(),
        samples=await usage.sample_count(),
        traffic=Metric(
            value=float(traffic),
            previous=float(traffic_prev),
            change_pct=pct_change(traffic, traffic_prev),
        ),
        traffic_counter_reset=window_traffic.counter_reset,
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
