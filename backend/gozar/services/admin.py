"""Admin service — the logic behind the owner-only bot panel (Phase 6).

Keeps every admin mutation out of the handlers (delivery → services → infra) so it stays
unit-testable: stats aggregation, the single-user actions (ban/unban, reclaim, zero-referrals), and
re-deriving the location allowlist from the trial squad. Bulk fan-out (broadcast/forward) and the
bulk traffic reset run in the arq worker, not here. Mutations flush on the per-update session and
commit with it; panel calls are single bounded attempts (log + move on, never a retry loop).
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass

from redis.asyncio import Redis

from gozar.cache.redis import limited_notified_key, sub_cache_key
from gozar.db.models.enums import UserStatus
from gozar.db.models.user import User
from gozar.db.repositories.config_log import ConfigLogRepository
from gozar.db.repositories.user import UserRepository
from gozar.remnawave import RemnawaveClient, RemnawaveError
from gozar.services.settings_service import SettingKey, SettingsService
from gozar.services.stats import start_of_today
from gozar.services.trial import _DEFAULT_TRIAL_HOURS, cooldown_start

logger = logging.getLogger("gozar.services.admin")


@dataclass(frozen=True)
class AdminStats:
    """Counts for the admin stats screen — all from the DB, no panel call."""

    total: int
    available: int
    active: int
    banned: int
    configs_today: int
    referrals: int


@dataclass(frozen=True)
class UserCard:
    """A looked-up user plus their lifetime claim count, for the admin user card."""

    user: User
    configs: int


class AdminService:
    def __init__(
        self,
        users: UserRepository,
        config_logs: ConfigLogRepository,
        settings: SettingsService,
        panel: RemnawaveClient,
        redis: Redis,
    ) -> None:
        self._users = users
        self._logs = config_logs
        self._settings = settings
        self._panel = panel
        self._redis = redis

    async def stats(self) -> AdminStats:
        return AdminStats(
            total=await self._users.count(),
            available=await self._users.count_by_status(UserStatus.available),
            active=await self._users.count_by_status(UserStatus.active_config),
            banned=await self._users.count_by_status(UserStatus.banned),
            # The operator's calendar day (Asia/Tehran), not UTC — a UTC midnight rolled this
            # counter over 3.5h early, so the first hours of every local day showed yesterday.
            configs_today=await self._logs.count_since(start_of_today()),
            referrals=await self._users.sum_referrals(),
        )

    async def lookup(self, target_id: int) -> UserCard | None:
        user = await self._users.get(target_id)
        if user is None:
            return None
        return UserCard(user=user, configs=await self._logs.count_for_user(target_id))

    async def ban(self, target_id: int) -> User | None:
        """Block in the bot AND revoke access now: best-effort delete the live panel user, then flip
        ``status -> banned`` (the middleware blocks every future update from a banned user)."""
        user = await self._users.get(target_id)
        if user is None:
            return None
        await self._revoke_panel(user)
        user.status = UserStatus.banned
        user.panel_username = None
        return user

    async def unban(self, target_id: int) -> User | None:
        user = await self._users.get(target_id)
        if user is None:
            return None
        user.status = UserStatus.available
        return user

    async def reclaim(self, target_id: int) -> User | None:
        """Forgiveness: clear the rolling claim cooldown + heal back to ``available`` so a stuck
        user can claim a fresh config again right away. Also DELETES the live panel account (best
        effort): a data-limited trial now keeps its account far longer, so reclaiming one without
        revoking it would orphan a live Remnawave user."""
        user = await self._users.get(target_id)
        if user is None:
            return None
        hours = max(await self._settings.get_int(SettingKey.TRIAL_HOURS, _DEFAULT_TRIAL_HOURS), 1)
        await self._logs.delete_for_user_since(target_id, cooldown_start(hours))
        await self._revoke_panel(user)  # delete the live panel account + drop the cached sub
        user.status = UserStatus.available
        user.panel_username = None
        user.last_claim_at = None  # clear the cooldown anchor too, so the guard frees them at once
        await self._redis.delete(limited_notified_key(target_id))
        return user

    async def zero_referrals(self, target_id: int) -> User | None:
        """Punitive: reset ``referral_count`` to 0 (drops their daily allowance to base)."""
        user = await self._users.get(target_id)
        if user is None:
            return None
        user.referral_count = 0
        return user

    async def refresh_locations(self) -> list[str] | None:
        """Re-derive the location allowlist from the trial squad and store it. Returns the names, or
        ``None`` if the squad isn't configured yet or the panel call fails."""
        squad = await self._settings.get(SettingKey.TRIAL_SQUAD)
        if not squad:
            logger.warning("refresh_locations: no trial squad configured")
            return None
        try:
            names = await self._panel.squad_location_names(squad)
        except RemnawaveError:
            logger.warning("refresh_locations: panel call failed")
            return None
        await self._settings.set(SettingKey.LOCATIONS, json.dumps(names))
        return names

    async def _revoke_panel(self, user: User) -> None:
        """Best-effort: drop the user's cached sub + delete their live panel account so a ban takes
        effect at once. Bounded single attempt — a panel error never blocks the ban."""
        await self._redis.delete(sub_cache_key(user.telegram_id))
        username = user.panel_username
        if not username:
            return
        try:
            panel_user = await self._panel.get_user(username)
            if panel_user is not None and panel_user.uuid:
                await self._panel.delete_user(panel_user.uuid)
        except RemnawaveError:
            logger.warning("ban: panel revoke failed for %s (left to expire)", user.telegram_id)
