"""Public reward endpoint: POST /rewards/claim (invite bonus is credited by the claim flow itself).

Handles the one-time PWA/notification grants and the daily-streak check-in. Guarded by a Redis rate
limit (one-time rewards are idempotent via the DB unique constraint; the streak is idempotent per
UTC day), so no Turnstile is needed here.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from gozar.db.repositories.push_subscription import PushSubscriptionRepository
from gozar.db.repositories.site_reward import SiteRewardRepository
from gozar.services.settings_service import SettingsService
from gozar.services.site_reward import SiteRewardService
from gozar.web.dependencies import DbSession
from gozar.web.routes.public.identity import CurrentDevice
from gozar.web.routes.public.security import rate_limit_ok

router = APIRouter(tags=["public"])

_REWARD_LIMIT = 20
_REWARD_WINDOW = 60


class RewardRequest(BaseModel):
    reward_type: str


class RewardResponse(BaseModel):
    ok: bool
    reason: str | None = None
    reward_type: str | None = None
    amount_mb: int | None = None
    streak_count: int | None = None
    streak_active: bool = False
    new_daily: str | None = None


@router.post("/rewards/claim", response_model=RewardResponse)
async def claim_reward(
    body: RewardRequest, request: Request, session: DbSession, device: CurrentDevice
) -> RewardResponse:
    redis = request.app.state.redis
    if not await rate_limit_ok(
        redis, "reward", device.uuid, limit=_REWARD_LIMIT, window_seconds=_REWARD_WINDOW
    ):
        raise HTTPException(status_code=429, detail="rate_limited")

    service = SiteRewardService(
        SiteRewardRepository(session),
        SettingsService(session, redis),
        request.app.state.panel,
        redis,
        PushSubscriptionRepository(session),
    )
    result = await service.claim(device, body.reward_type)
    return RewardResponse(
        ok=result.ok,
        reason=result.reason,
        reward_type=result.reward_type,
        amount_mb=result.amount_mb,
        streak_count=result.streak_count,
        streak_active=result.streak_active,
        new_daily=result.new_daily,
    )
