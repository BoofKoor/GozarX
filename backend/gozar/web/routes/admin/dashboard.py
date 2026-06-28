"""Dashboard (auth-gated): headline counts + activity/growth series + breakdowns for the panel.

Counts reuse Phase 6 ``AdminService.stats()`` so the panel and the in-bot ``/admin`` never drift.
The chart series, language/location breakdowns, and top referrers are cheap grouped queries over the
same per-request session. ``online_now`` is the trial-squad users the panel reports as online,
intersected with our DB; it falls back to the DB active-config count when the panel can't answer.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Query, Request
from pydantic import BaseModel

from gozar.db.models.enums import UserStatus
from gozar.db.repositories.config_log import ConfigLogRepository
from gozar.db.repositories.user import UserRepository
from gozar.remnawave import RemnawaveClient, RemnawaveError
from gozar.services.admin import AdminService
from gozar.services.settings_service import SettingsService
from gozar.web.dependencies import AdminUser, DbSession

router = APIRouter(prefix="/dashboard", tags=["dashboard"])

_ALLOWED_RANGES = (7, 14, 30)
_DEFAULT_RANGE = 14


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
    total_users: int
    available: int
    active: int
    banned: int
    configs_today: int
    referrals: int
    online_now: int
    range_days: int
    claims_series: list[DayPoint]
    signups_series: list[DayPoint]
    languages: list[NamedCount]
    top_locations: list[NamedCount]
    top_referrers: list[Referrer]


async def _online_now(panel: RemnawaveClient, users: UserRepository, fallback: int) -> int:
    """Our trial-squad users currently online per the panel (∩ our active panel usernames). A single
    bounded attempt — fall back to the DB active-config count if the panel can't answer."""
    try:
        online = await panel.online_usernames()
    except RemnawaveError:
        return fallback
    if online is None:
        return fallback
    ours = set(await users.list_panel_usernames_by_status(UserStatus.active_config))
    return len(online & ours)


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
    since = datetime.now(UTC) - timedelta(days=window)
    claims = await config_log_repo.daily_counts(since)
    signups = await user_repo.signups_daily(since)
    languages = await user_repo.language_breakdown()
    top_locations = await config_log_repo.location_counts(since)
    referrers = await user_repo.top_referrers()
    online_now = await _online_now(panel, user_repo, s.active)
    return DashboardOut(
        total_users=s.total,
        available=s.available,
        active=s.active,
        banned=s.banned,
        configs_today=s.configs_today,
        referrals=s.referrals,
        online_now=online_now,
        range_days=window,
        claims_series=[DayPoint(day=d, count=n) for d, n in claims],
        signups_series=[DayPoint(day=d, count=n) for d, n in signups],
        languages=[NamedCount(label=lang, count=n) for lang, n in languages],
        top_locations=[NamedCount(label=loc, count=n) for loc, n in top_locations],
        top_referrers=[Referrer(telegram_id=t, referral_count=n) for t, n in referrers],
    )
