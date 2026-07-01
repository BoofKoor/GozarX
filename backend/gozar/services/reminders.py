"""Reminder service — turn an ended trial into a reset + a reminder to send.

Triggered by ``user.expired`` / ``user.limited`` (panel webhook) or a panel state that reads
EXPIRED / LIMITED / missing (the worker's ``reconcile_trials`` fallback). We map the panel user back
to its Gozar user, reset them to ``available`` so they can claim again once the cooldown elapses
(clearing the SAME ``cache:sub:{tid}`` key the trial service's lazy self-heal uses), and report the
reminder copy + tokens to send. The reset is unconditional for a non-banned holder; the message is
gated on ``reminder_enabled`` by the caller. A banned user is never touched.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

from redis.asyncio import Redis

from gozar.cache.redis import limited_notified_key, sub_cache_key
from gozar.db.models.enums import UserStatus
from gozar.db.models.user import User
from gozar.db.repositories.config_log import ConfigLogRepository
from gozar.db.repositories.user import UserRepository
from gozar.remnawave import RemnawaveClient, RemnawaveError
from gozar.remnawave.schemas import WebhookUserEvent
from gozar.services.settings_service import SettingKey, SettingsService
from gozar.services.trial import _DEFAULT_TRIAL_HOURS, cooldown_remaining

logger = logging.getLogger("gozar.services.reminders")

# VERIFY: Remnawave's event names for the expiry / data-limit transitions.
_REMINDER_FOR_EVENT = {
    "user.expired": "reminder_expired",
    "user.limited": "reminder_limited",
}


@dataclass(frozen=True)
class ReminderOutcome:
    """The matched user + which reminder copy to send + its render tokens.

    The caller gates the send on ``reminder_enabled``. ``tokens`` already carries
    ``cooldown_remaining`` (time left until the next claim is allowed) merged with whatever
    panel-derived tokens the caller passed in.
    """

    user: User
    content_key: str
    tokens: dict[str, str]


class ReminderService:
    def __init__(
        self,
        user_repo: UserRepository,
        config_logs: ConfigLogRepository,
        settings: SettingsService,
        redis: Redis,
        panel: RemnawaveClient | None = None,
    ) -> None:
        self._users = user_repo
        self._logs = config_logs
        self._settings = settings
        self._redis = redis
        self._panel = panel

    async def _cooldown_remaining(self, telegram_id: int) -> str:
        hours = max(await self._settings.get_int(SettingKey.TRIAL_HOURS, _DEFAULT_TRIAL_HOURS), 1)
        last = await self._logs.latest_created_at_for_user(telegram_id)
        return cooldown_remaining(last, hours)

    async def _delete_panel_user(self, user: User) -> None:
        """Best-effort: delete the ended trial's Remnawave account so expired users don't pile up in
        the panel (an expired user is only DISABLED there, never auto-removed). Bounded single
        attempt — a panel error is logged and ignored so the reset/reminder still proceeds."""
        username = user.panel_username
        if not self._panel or not username:
            return
        try:
            await self._panel.delete_user_by_username(username)
        except RemnawaveError:
            logger.warning(
                "reminder: panel delete failed for %s (left to expire)", user.telegram_id
            )

    async def _reset_and_outcome(
        self, user: User, content_key: str, base_tokens: dict[str, str]
    ) -> ReminderOutcome:
        # TIME-expiry teardown: delete the panel account, reset to claimable (proactive counterpart
        # to the lazy self-heal, same cache key), and drop the data-limit nudge guard for next time.
        await self._delete_panel_user(user)  # remove the ended trial from the panel first
        user.status = UserStatus.available
        user.panel_username = None
        await self._redis.delete(sub_cache_key(user.telegram_id))
        await self._redis.delete(limited_notified_key(user.telegram_id))
        cooldown = await self._cooldown_remaining(user.telegram_id)
        tokens = {**base_tokens, "cooldown_remaining": cooldown}
        return ReminderOutcome(user=user, content_key=content_key, tokens=tokens)

    async def _limited_outcome(
        self, user: User, base_tokens: dict[str, str]
    ) -> ReminderOutcome | None:
        # DATA ran out but TIME is still valid: keep the panel account + active_config so a referral
        # bump can revive the SAME config. Fire the 'invite to revive' nudge at most ONCE per
        # episode (SET NX; the status transition no longer guards it). No delete, no state reset.
        hours = max(await self._settings.get_int(SettingKey.TRIAL_HOURS, _DEFAULT_TRIAL_HOURS), 1)
        first = await self._redis.set(
            limited_notified_key(user.telegram_id), "1", ex=hours * 3600, nx=True
        )
        if not first:  # already nudged this episode — don't spam
            return None
        cooldown = await self._cooldown_remaining(user.telegram_id)
        tokens = {**base_tokens, "cooldown_remaining": cooldown}
        return ReminderOutcome(user=user, content_key="reminder_limited", tokens=tokens)

    async def apply_event(
        self, event: WebhookUserEvent, base_tokens: dict[str, str] | None = None
    ) -> ReminderOutcome | None:
        """Webhook path: a ``user.expired`` / ``user.limited`` event mapped to its Gozar user."""
        content_key = _REMINDER_FOR_EVENT.get(event.event)
        if content_key is None:  # not an expiry/limit event — ignore
            return None
        username = event.data.username
        if not username:
            return None
        user = await self._users.get_by_panel_username(username)
        if user is None or user.status is UserStatus.banned:
            return None
        if event.event == "user.limited":
            return await self._limited_outcome(user, base_tokens or {})
        return await self._reset_and_outcome(user, content_key, base_tokens or {})

    async def apply_ended_trial(
        self, user: User, base_tokens: dict[str, str] | None = None
    ) -> ReminderOutcome | None:
        """Reconcile path: a known ``active_config`` user whose live trial is TERMINAL.

        The sweep only reaches here for a genuinely ended trial (time-expired / disabled / missing);
        a data-limited-but-time-valid trial is filtered out upstream by ``_is_expired``,
        so this is always an expiry reset (delete + reset + ``reminder_expired``). The data-limit
        'invite to revive' nudge is webhook-only. A user already reset by the webhook is skipped, so
        the sweep never double-notifies.
        """
        if user.status is not UserStatus.active_config:
            return None
        return await self._reset_and_outcome(user, "reminder_expired", base_tokens or {})
