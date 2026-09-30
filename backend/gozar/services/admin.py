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


class ReclaimRefused(Exception):
    """A reclaim — or an unban — that must not happen. ``reason`` is ``"banned"`` (reclaiming would
    silently lift the ban) or ``"panel"`` (the live account could not be revoked, so going ahead
    would hand the user a second trial while the first still works)."""

    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


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
        """Block in the bot AND revoke access now: delete the live panel user, then flip
        ``status -> banned`` (the middleware blocks every future update from a banned user).

        The ban itself always applies. The panel handle is cleared ONLY once the account is gone:
        when the panel cannot be reached the user keeps a working config until the delete lands, and
        forgetting the handle then (as this used to) made that account impossible to revoke ever —
        nothing maps a panel user back to a row without it. A banned user who still carries a
        ``panel_username`` is therefore exactly "revoke pending"; the reconcile sweep retries it and
        the panel shows it to the operator.
        """
        user = await self._users.get(target_id)
        if user is None:
            return None
        revoked = await self._revoke_panel(user)
        user.status = UserStatus.banned
        if revoked:
            user.panel_username = None
        return user

    async def unban(self, target_id: int) -> User | None:
        """Lift a ban. A revoke still pending from the ban (the handle kept because the panel did
        not answer) has to land first: unbanned with it, the user was ``available`` while the old
        account still worked — and the sweep only retries a BANNED user's revoke, so nothing ever
        would — and their next claim gave them a second live trial beside it. Refused
        (``ReclaimRefused("panel")``, nothing changed) while the panel still cannot be reached.

        A user who is not banned is left as they are: forcing an ``active_config`` user to
        ``available`` hid their live config from ``/status`` and from the reconcile sweep.
        """
        user = await self._users.get(target_id)
        if user is None:
            return None
        if user.status is not UserStatus.banned:
            return user
        if user.panel_username:
            if not await self._revoke_panel(user):
                raise ReclaimRefused("panel")
            user.panel_username = None
        user.status = UserStatus.available
        return user

    async def reclaim(self, target_id: int) -> User | None:
        """Forgiveness: clear the rolling claim cooldown + heal back to ``available`` so a stuck
        user can claim a fresh config again right away. Also DELETES the live panel account: a
        data-limited trial keeps its account far longer, so reclaiming one without revoking it would
        orphan a live Remnawave user.

        Refused (``ReclaimRefused``) for a banned user — it used to flip them to ``available``,
        which is an unban nobody asked for — and when the panel cannot be reached, because clearing
        the cooldown while the old account still works hands out a second concurrent trial.

        The claim HISTORY is left alone. Clearing ``last_claim_at`` is what frees the cooldown; the
        rows this used to delete were the dashboard's record of claims that really happened.
        """
        user = await self._users.get(target_id)
        if user is None:
            return None
        if user.status is UserStatus.banned:
            raise ReclaimRefused("banned")
        if not await self._revoke_panel(user):  # delete the live account + drop the cached sub
            raise ReclaimRefused("panel")
        user.status = UserStatus.available
        user.panel_username = None
        user.last_claim_at = None  # the cooldown anchor: clearing it frees the guard at once
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
        """Offer every location the trial squad serves, from now on. Returns the squad's current
        names, or ``None`` if the squad isn't configured yet or the panel call fails.

        Stores ``[]`` ("all of them") rather than today's names: a snapshot froze out every host
        added afterwards, and went stale — blocking the next settings save with a 400 — the moment
        a host it named was renamed or hidden. A squad that serves nothing leaves the list as it is.
        """
        squad = await self._settings.get(SettingKey.TRIAL_SQUAD)
        if not squad:
            logger.warning("refresh_locations: no trial squad configured")
            return None
        try:
            names = await self._panel.squad_location_names(squad)
        except RemnawaveError:
            logger.warning("refresh_locations: panel call failed")
            return None
        if names:
            await self._settings.set(SettingKey.LOCATIONS, json.dumps([]))
        return names

    async def _revoke_panel(self, user: User) -> bool:
        """Drop the user's cached sub + delete their live panel account. True once no live account
        remains (deleted, already gone, or never had one); False when the panel could not be
        reached. Bounded single attempt — the caller decides what a failure means."""
        await self._redis.delete(sub_cache_key(user.telegram_id))
        username = user.panel_username
        if not username:
            return True
        try:
            panel_user = await self._panel.get_user(username)  # None on 404: already gone
            if panel_user is not None and panel_user.ref:  # uuid on panel 2.x, numeric id on 3.x
                await self._panel.delete_user(panel_user.ref)
        except RemnawaveError:
            logger.warning("admin: panel revoke failed for %s (kept pending)", user.telegram_id)
            return False
        return True
