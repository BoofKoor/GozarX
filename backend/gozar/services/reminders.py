"""Reminder service — turn Remnawave panel webhook events into a user reset + a reminder to send.

On ``user.expired`` / ``user.limited`` we map the panel username back to its Gozar user, reset them
to ``available`` so they can claim again (the proactive counterpart to the trial service's lazy
self-heal — clearing the SAME ``cache:sub:{tid}`` key), and report which reminder copy to send. The
reset is unconditional for a non-banned holder; the message is gated on ``reminder_enabled`` by the
caller. A banned user is never touched (never un-banned, never messaged).
"""

from __future__ import annotations

from dataclasses import dataclass

from redis.asyncio import Redis

from gozar.cache.redis import sub_cache_key
from gozar.db.models.enums import UserStatus
from gozar.db.models.user import User
from gozar.db.repositories.user import UserRepository
from gozar.remnawave.schemas import WebhookUserEvent

# VERIFY: Remnawave's event names for the expiry / data-limit transitions.
_REMINDER_FOR_EVENT = {
    "user.expired": "reminder_expired",
    "user.limited": "reminder_limited",
}


@dataclass(frozen=True)
class ReminderOutcome:
    """The matched user + which reminder copy to send (the route gates on reminder_enabled)."""

    user: User
    content_key: str


class ReminderService:
    def __init__(self, user_repo: UserRepository, redis: Redis) -> None:
        self._users = user_repo
        self._redis = redis

    async def apply_event(self, event: WebhookUserEvent) -> ReminderOutcome | None:
        content_key = _REMINDER_FOR_EVENT.get(event.event)
        if content_key is None:  # not an expiry/limit event — ignore
            return None
        username = event.data.username
        if not username:
            return None
        user = await self._users.get_by_panel_username(username)
        if user is None or user.status is UserStatus.banned:
            return None
        # Reset to claimable — proactive counterpart to the lazy self-heal (same cache key).
        user.status = UserStatus.available
        user.panel_username = None
        await self._redis.delete(sub_cache_key(user.telegram_id))
        return ReminderOutcome(user=user, content_key=content_key)
