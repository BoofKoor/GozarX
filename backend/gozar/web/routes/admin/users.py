"""Admin users (auth-gated) — list/search + per-user card + the Phase 6 actions over HTTP.

Pure delivery: every mutation reuses ``AdminService`` (ban/unban/reclaim/zero-referrals), so the web
panel and the in-bot ``/admin`` never drift. GozarX is a free tool — there is no billing surface.
"""

from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, HTTPException, Query, Request
from pydantic import BaseModel

from gozar.db.models.enums import UserStatus
from gozar.db.models.user import User
from gozar.db.repositories.config_log import ConfigLogRepository
from gozar.db.repositories.user import UserRepository
from gozar.services.admin import AdminService
from gozar.services.settings_service import SettingsService
from gozar.web.dependencies import AdminUser, DbSession

router = APIRouter(prefix="/users", tags=["users"])


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
    configs: int | None = None  # lifetime claims — set on the detail card only


class UserPage(BaseModel):
    items: list[UserOut]
    total: int
    page: int
    page_size: int


def _out(user: User, configs: int | None = None) -> UserOut:
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
) -> UserPage:
    repo = UserRepository(session)
    offset = (page - 1) * page_size
    items = await repo.list_page(limit=page_size, offset=offset, status=status, search=search)
    total = await repo.count_filtered(status=status, search=search)
    return UserPage(items=[_out(u) for u in items], total=total, page=page, page_size=page_size)


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
