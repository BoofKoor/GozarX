"""Dashboard (auth-gated): headline counts + a daily-claims activity series for the chart.

Counts reuse Phase 6 ``AdminService.stats()`` so the panel and the in-bot ``/admin`` never drift.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Request
from pydantic import BaseModel

from gozar.db.repositories.config_log import ConfigLogRepository
from gozar.db.repositories.user import UserRepository
from gozar.services.admin import AdminService
from gozar.services.settings_service import SettingsService
from gozar.web.dependencies import AdminUser, DbSession

router = APIRouter(prefix="/dashboard", tags=["dashboard"])

_SERIES_DAYS = 14


class DayPoint(BaseModel):
    day: str
    count: int


class DashboardOut(BaseModel):
    total_users: int
    available: int
    active: int
    banned: int
    configs_today: int
    referrals: int
    claims_series: list[DayPoint]


@router.get("/stats", response_model=DashboardOut)
async def dashboard_stats(request: Request, session: DbSession, admin: AdminUser) -> DashboardOut:
    user_repo = UserRepository(session)
    config_log_repo = ConfigLogRepository(session)
    settings = SettingsService(session, request.app.state.redis)
    admin_svc = AdminService(
        user_repo, config_log_repo, settings, request.app.state.panel, request.app.state.redis
    )
    s = await admin_svc.stats()
    since = datetime.now(UTC) - timedelta(days=_SERIES_DAYS)
    series = await config_log_repo.daily_counts(since)
    return DashboardOut(
        total_users=s.total,
        available=s.available,
        active=s.active,
        banned=s.banned,
        configs_today=s.configs_today,
        referrals=s.referrals,
        claims_series=[DayPoint(day=d, count=n) for d, n in series],
    )
