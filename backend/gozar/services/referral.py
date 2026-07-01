"""Referral awarding — credit the inviter when an invited friend claims their first config.

Runs inside the **invitee's request session** (the middleware's single session): the inviter is
loaded via the SAME ``user_repo``, so the inviter's ``referral_count += 1`` and the invitee's
``config_log`` insert are flushed and committed together by the one middleware commit. There is no
second/short-lived session, so the +1 can't be dropped and a commit failure rolls back both.

If the inviter currently holds a live trial we also raise its panel traffic limit immediately
(``PATCH /users`` keys off the uuid, so we fetch the user by username first — finding #4). That bump
is best-effort: one bounded call, logged and ignored on failure (the inviter's next claim recomputes
the allowance from the new count regardless).
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

from redis.asyncio import Redis

from gozar.cache.redis import limited_notified_key, sub_cache_key
from gozar.db.models.enums import UserStatus
from gozar.db.models.user import User
from gozar.db.repositories.user import UserRepository
from gozar.remnawave import RemnawaveClient, RemnawaveError
from gozar.services.settings_service import SettingsService
from gozar.services.trial import compute_traffic_bytes

logger = logging.getLogger("gozar.services.referral")


@dataclass(frozen=True)
class AwardResult:
    """A credited referral — carried back so the handler can notify the inviter post-commit.

    ``new_daily_bytes`` is the inviter's recomputed allowance (capped bonus already applied), so the
    notice can quote a number that's always accurate — even once they're past the reward cap.
    """

    inviter: User
    new_count: int
    new_daily_bytes: int


class ReferralService:
    def __init__(
        self,
        user_repo: UserRepository,
        settings: SettingsService,
        panel: RemnawaveClient,
        redis: Redis | None = None,
    ) -> None:
        self._users = user_repo
        self._settings = settings
        self._panel = panel
        self._redis = redis

    async def award_first_claim(self, invitee: User) -> AwardResult | None:
        """Credit the invitee's referrer (caller guarantees this is the invitee's first claim).

        Resolves + credits the inviter via the same session as the invitee; returns the award (for
        the post-commit notice) or ``None`` when there is no one to credit.
        """
        if not invitee.referred_by:
            return None
        inviter = await self._users.get(invitee.referred_by)
        if inviter is None or inviter.status is UserStatus.banned:
            return None

        inviter.referral_count += 1  # managed entity — persists on the middleware commit
        new_daily_bytes = await compute_traffic_bytes(self._settings, inviter.referral_count)
        await self._maybe_bump_live_trial(inviter, new_daily_bytes)
        return AwardResult(
            inviter=inviter, new_count=inviter.referral_count, new_daily_bytes=new_daily_bytes
        )

    async def _maybe_bump_live_trial(self, inviter: User, new_daily_bytes: int) -> None:
        """Raise the inviter's live-trial panel limit to the new allowance, if they hold one.

        This is also the REVIVE path for a data-exhausted (LIMITED-but-time-valid) inviter: because
        such a user is now kept ``active_config`` with a live panel account (see TrialService), this
        guard passes and the bump lifts their cap. VERIFY: on the panel versions we target, raising
        ``trafficLimitBytes`` above ``usedTrafficBytes`` re-activates a LIMITED user on the next
        node sync — reviving the SAME config. We do NOT reset usage (that would refund already-spent
        traffic). On a successful bump we drop the one-shot data-limit nudge guard + the cached sub
        so the next status read reflects the revived state.
        """
        if inviter.status is not UserStatus.active_config or not inviter.panel_username:
            return
        try:
            panel_user = await self._panel.get_user(inviter.panel_username)
            if panel_user and panel_user.uuid:
                await self._panel.update_traffic_limit(panel_user.uuid, new_daily_bytes)
                if self._redis is not None:
                    await self._redis.delete(limited_notified_key(inviter.telegram_id))
                    await self._redis.delete(sub_cache_key(inviter.telegram_id))
        except RemnawaveError:
            logger.warning("referral live-bump failed for inviter %s", inviter.telegram_id)
