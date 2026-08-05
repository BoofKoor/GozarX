"""Admin users (auth-gated) — list/search + per-user card + the Phase 6 actions over HTTP.

Pure delivery: every mutation reuses ``AdminService`` (ban/unban/reclaim/zero-referrals), so the web
panel and the in-bot ``/admin`` never drift. GozarX is a free tool — there is no billing surface.
"""

from __future__ import annotations

import csv
import io
import logging
from datetime import datetime

from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel

from gozar.db.models.enums import UserStatus
from gozar.db.models.user import User
from gozar.db.repositories.config_log import ConfigLogRepository
from gozar.db.repositories.user import UserRepository
from gozar.services.admin import AdminService
from gozar.services.settings_service import SettingsService
from gozar.services.stats import window_start, zero_filled_daily
from gozar.web.dependencies import AdminUser, DbSession

log = logging.getLogger(__name__)

router = APIRouter(prefix="/users", tags=["users"])

#: How far back the record dialog's mini chart looks.
_DETAIL_DAYS = 30
#: A ceiling on the export, so one click can never stream the whole table into a request thread.
_EXPORT_LIMIT = 50_000


def _admin_service(request: Request, session: object) -> AdminService:
    redis = request.app.state.redis
    return AdminService(
        UserRepository(session),  # type: ignore[arg-type]
        ConfigLogRepository(session),  # type: ignore[arg-type]
        SettingsService(session, redis),  # type: ignore[arg-type]
        request.app.state.panel,
        redis,
    )


class UserOut(BaseModel):
    telegram_id: int
    status: str
    language: str
    referral_count: int
    panel_username: str | None
    reminder_enabled: bool
    referred_by: int | None
    created_at: datetime | None
    #: Lifetime claims. The design's users table leads with this and with recency, because "who is
    #: this person to the service" is the question the row is opened to answer — a panel username
    #: and a signup date say only that the row exists.
    configs: int | None = None
    #: Where this user's LATEST claim came from. None until they have claimed once.
    last_location: str | None = None
    #: When that claim was provisioned — the rolling-cooldown anchor, and the row's recency signal.
    last_claim_at: datetime | None = None


class UserPage(BaseModel):
    items: list[UserOut]
    total: int
    page: int
    page_size: int


class ClaimOut(BaseModel):
    location: str
    created_at: datetime


class DayCount(BaseModel):
    day: str
    count: int


class UserDetailOut(UserOut):
    """Everything the record dialog shows beyond the row it was opened from."""

    #: One entry per day in the window, zero-filled, so the chart has no gaps to interpolate over.
    claims_series: list[DayCount] = []
    recent_claims: list[ClaimOut] = []
    #: Live usage, read from the panel. NULL when the user has no panel account or the panel did not
    #: answer — a single bounded attempt, never a retry loop, and never a zero standing in for
    #: "unknown".
    traffic_bytes: int | None = None


def _out(user: User, configs: int | None = None, last_location: str | None = None) -> UserOut:
    return UserOut(
        telegram_id=user.telegram_id,
        status=user.status.value,
        language=user.language.value,
        referral_count=user.referral_count,
        panel_username=user.panel_username,
        reminder_enabled=user.reminder_enabled,
        referred_by=user.referred_by,
        created_at=user.created_at,
        configs=configs,
        last_location=last_location,
        last_claim_at=user.last_claim_at,
    )


@router.get("/", response_model=UserPage)
async def list_users(
    request: Request,
    session: DbSession,
    admin: AdminUser,
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=100),
    status: UserStatus | None = None,
    search: str | None = None,
    location: str | None = None,
) -> UserPage:
    repo = UserRepository(session)
    offset = (page - 1) * page_size
    items = await repo.list_page(
        limit=page_size, offset=offset, status=status, search=search, location=location
    )
    total = await repo.count_filtered(status=status, search=search, location=location)
    # Two extra queries for the whole page, not two per row.
    ids = [u.telegram_id for u in items]
    logs = ConfigLogRepository(session)
    places = await logs.latest_locations(ids)
    counts = await logs.counts_for(ids)
    return UserPage(
        items=[
            _out(u, configs=counts.get(u.telegram_id, 0), last_location=places.get(u.telegram_id))
            for u in items
        ],
        total=total,
        page=page,
        page_size=page_size,
    )


# Declared BEFORE `/{telegram_id}`: FastAPI matches in declaration order, and an int-typed path
# parameter would otherwise swallow "locations" and "export.csv" and answer 422.
@router.get("/locations", response_model=list[str])
async def claimed_locations(session: DbSession, admin: AdminUser) -> list[str]:
    """Locations the users list can be filtered by — every one a config was ever claimed from."""
    return await ConfigLogRepository(session).distinct_locations()


@router.get("/export.csv", response_class=PlainTextResponse)
async def export_users(
    session: DbSession,
    admin: AdminUser,
    status: UserStatus | None = None,
    search: str | None = None,
    location: str | None = None,
) -> PlainTextResponse:
    """The CURRENT filter's users as CSV.

    It exports what the table is showing, not the whole table: an operator filters to a case and
    then wants that case out, and an export that silently ignores the filters is a different
    question's answer. Written with `csv` rather than string joins so a location containing a comma
    can never shift the columns.
    """
    repo = UserRepository(session)
    rows = await repo.list_page(
        limit=_EXPORT_LIMIT, offset=0, status=status, search=search, location=location
    )
    places = await ConfigLogRepository(session).latest_locations([u.telegram_id for u in rows])

    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(
        ["telegram_id", "status", "language", "referrals", "panel_username", "location", "joined"]
    )
    for user in rows:
        writer.writerow(
            [
                user.telegram_id,
                user.status.value,
                user.language.value,
                user.referral_count,
                user.panel_username or "",
                places.get(user.telegram_id, ""),
                user.created_at.isoformat() if user.created_at else "",
            ]
        )
    return PlainTextResponse(
        buffer.getvalue(),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": 'attachment; filename="gozar-users.csv"'},
    )


@router.get("/{telegram_id}/detail", response_model=UserDetailOut)
async def get_user_detail(
    telegram_id: int, request: Request, session: DbSession, admin: AdminUser
) -> UserDetailOut:
    """The record dialog: the row, plus this user's claim history and live traffic."""
    card = await _admin_service(request, session).lookup(telegram_id)
    if card is None:
        raise HTTPException(404, "user not found")

    logs = ConfigLogRepository(session)
    since = window_start(_DETAIL_DAYS)
    counts = dict(await logs.daily_counts_for_user(telegram_id, since))
    recent = await logs.recent_for_user(telegram_id)
    places = await logs.latest_locations([telegram_id])

    traffic: int | None = None
    if card.user.panel_username:
        # One bounded attempt. The panel being down must not make a record unopenable, so a failure
        # leaves the figure NULL and the dialog says so.
        try:
            panel_user = await request.app.state.panel.get_user(card.user.panel_username)
            traffic = panel_user.traffic.used_bytes if panel_user else None
        except Exception:  # noqa: BLE001 — any panel failure is the same answer here
            log.warning("panel lookup failed for user %s", telegram_id)

    base = _out(card.user, configs=card.configs, last_location=places.get(telegram_id))
    return UserDetailOut(
        **base.model_dump(),
        claims_series=[
            DayCount(day=day, count=n)
            for day, n in zero_filled_daily(list(counts.items()), since=since, days=_DETAIL_DAYS)
        ],
        recent_claims=[ClaimOut(location=r.location, created_at=r.created_at) for r in recent],
        traffic_bytes=traffic,
    )


@router.get("/{telegram_id}", response_model=UserOut)
async def get_user(
    telegram_id: int, request: Request, session: DbSession, admin: AdminUser
) -> UserOut:
    card = await _admin_service(request, session).lookup(telegram_id)
    if card is None:
        raise HTTPException(404, "user not found")
    return _out(card.user, configs=card.configs)


async def _run_action(request: Request, session: object, telegram_id: int, method: str) -> UserOut:
    svc = _admin_service(request, session)
    user = await getattr(svc, method)(telegram_id)
    if user is None:
        raise HTTPException(404, "user not found")
    card = await svc.lookup(telegram_id)
    return _out(card.user, configs=card.configs) if card else _out(user)


@router.post("/{telegram_id}/ban", response_model=UserOut)
async def ban_user(
    telegram_id: int, request: Request, session: DbSession, admin: AdminUser
) -> UserOut:
    return await _run_action(request, session, telegram_id, "ban")


@router.post("/{telegram_id}/unban", response_model=UserOut)
async def unban_user(
    telegram_id: int, request: Request, session: DbSession, admin: AdminUser
) -> UserOut:
    return await _run_action(request, session, telegram_id, "unban")


@router.post("/{telegram_id}/reclaim", response_model=UserOut)
async def reclaim_user(
    telegram_id: int, request: Request, session: DbSession, admin: AdminUser
) -> UserOut:
    return await _run_action(request, session, telegram_id, "reclaim")


@router.post("/{telegram_id}/zero_referrals", response_model=UserOut)
async def zero_referrals_user(
    telegram_id: int, request: Request, session: DbSession, admin: AdminUser
) -> UserOut:
    return await _run_action(request, session, telegram_id, "zero_referrals")
