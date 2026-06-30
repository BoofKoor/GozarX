"""Reminder service — turn an ended trial into a reset + a reminder to send.

Triggered by ``user.expired`` / ``user.limited`` (panel webhook) or a panel state that reads
EXPIRED / LIMITED / missing (the worker's ``reconcile_trials`` fallback). We map the panel user back
to its Gozar user, reset them to ``available`` so they can claim again once the cooldown elapses
(clearing the SAME ``cache:sub:{tid}`` key the trial service's lazy self-heal uses), and report the
reminder copy + tokens to send. The reset is unconditional for a non-banned holder; the message is
gated on ``reminder_enabled`` by the caller. A banned user is never touched.
"""

from __future__ import annotations

from dataclasses import dataclass

from redis.asyncio import Redis

from gozar.cache.redis import sub_cache_key
from gozar.db.models.enums import UserStatus
from gozar.db.models.user import User
from gozar.db.repositories.config_log import ConfigLogRepository
from gozar.db.repositories.user import UserRepository
from gozar.remnawave.schemas import WebhookUserEvent
from gozar.services.settings_service import SettingKey, SettingsService
from gozar.services.trial import _DEFAULT_TRIAL_HOURS, cooldown_remaining

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
    panel-derived tokens the caller passed in. ``panel_username`` is the spent trial user the
    caller should purge from the panel AFTER the reset commits (best-effort cleanup); it is the
    username captured BEFORE the reset cleared it, so it is always one of our own trial users.
    """

    user: User
    content_key: str
    tokens: dict[str, str]
    panel_username: str | None


class ReminderService:
    def __init__(
        self,
        user_repo: UserRepository,
        config_logs: ConfigLogRepository,
        settings: SettingsService,
        redis: Redis,
    ) -> None:
        self._users = user_repo
        self._logs = config_logs
        self._settings = settings
        self._redis = redis

    async def _cooldown_remaining(self, telegram_id: int) -> str:
        hours = max(await self._settings.get_int(SettingKey.TRIAL_HOURS, _DEFAULT_TRIAL_HOURS), 1)
        last = await self._logs.latest_created_at_for_user(telegram_id)
        return cooldown_remaining(last, hours)

    async def _reset_and_outcome(
        self, user: User, content_key: str, base_tokens: dict[str, str]
    ) -> ReminderOutcome:
        # Reset to claimable — proactive counterpart to the lazy self-heal (same cache key).
        panel_username = user.panel_username  # capture before the reset clears it (for cleanup)
        user.status = UserStatus.available
        user.panel_username = None
        await self._redis.delete(sub_cache_key(user.telegram_id))
        cooldown = await self._cooldown_remaining(user.telegram_id)
        tokens = {**base_tokens, "cooldown_remaining": cooldown}
        return ReminderOutcome(
            user=user, content_key=content_key, tokens=tokens, panel_username=panel_username
        )

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
        return await self._reset_and_outcome(user, content_key, base_tokens or {})

    async def apply_ended_trial(
        self, user: User, panel_status: str, base_tokens: dict[str, str] | None = None
    ) -> ReminderOutcome | None:
        """Reconcile path: a known ``active_config`` user whose live panel trial has ended.

        ``panel_status`` is the panel's user status (``LIMITED`` ⇒ data reminder, anything else ⇒
        expiry reminder). A user who isn't holding a config (already reset by the webhook) is
        skipped, so the sweep never double-notifies.
        """
        if user.status is not UserStatus.active_config:
            return None
        limited = panel_status.upper() == "LIMITED"
        content_key = "reminder_limited" if limited else "reminder_expired"
        return await self._reset_and_outcome(user, content_key, base_tokens or {})
