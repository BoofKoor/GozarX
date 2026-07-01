"""Worker reconcile sweep — the panel-webhook fallback.

``reconcile_trials`` reads ``active_config`` users, probes the panel, and for any ended/limited
trial resets the user to claimable + sends the matching reminder. It must leave live trials alone
and never double-notify (idempotent with the webhook). DB-gated (real sessions via ``db_sessions``)
with a fake panel + fake bot + fakeredis.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import fakeredis.aioredis

from gozar.db.models.enums import UserStatus
from gozar.db.models.user import User
from gozar.db.repositories.user import UserRepository
from gozar.remnawave.schemas import Subscription, SubscriptionUser
from gozar.worker.tasks import reconcile_trials


def _sub(status: str) -> tuple[Subscription, dict]:
    expires = (datetime.now(UTC) + timedelta(hours=12)).isoformat()
    sub = Subscription(
        is_found=True,
        user=SubscriptionUser(
            user_status=status,
            expires_at=expires,
            traffic_used_bytes=1024**3,
            traffic_limit_bytes=1024**3,
            short_uuid="su",
        ),
    )
    return sub, {}


class FakePanel:
    """Maps a panel username to its current subscription status."""

    def __init__(self, by_username: dict[str, str]) -> None:
        self._by_username = by_username
        self.probed: list[str] = []
        self.deleted: list[str] = []

    async def subscription(self, username: str):
        self.probed.append(username)
        return _sub(self._by_username[username])

    async def delete_user_by_username(self, username: str) -> bool:
        self.deleted.append(username)
        return True


class FakeBot:
    def __init__(self) -> None:
        self.sent: list[int] = []

    async def send_message(self, chat_id: int, text: str, link_preview_options=None) -> None:
        self.sent.append(chat_id)


async def _add(sessionmaker, telegram_id: int, username: str) -> None:
    async with sessionmaker() as session:
        session.add(
            User(
                telegram_id=telegram_id,
                status=UserStatus.active_config,
                panel_username=username,
            )
        )
        await session.commit()


async def _status(sessionmaker, telegram_id: int) -> UserStatus:
    async with sessionmaker() as session:
        user = await UserRepository(session).get(telegram_id)
        return user.status


async def test_reconcile_resets_and_notifies_ended_trial_only(db_sessions) -> None:
    await _add(db_sessions, 1, "g1")  # data ran out
    await _add(db_sessions, 2, "g2")  # still live

    bot = FakeBot()
    ctx = {
        "sessionmaker": db_sessions,
        "panel": FakePanel({"g1": "LIMITED", "g2": "ACTIVE"}),
        "bot": bot,
        "cache_redis": fakeredis.aioredis.FakeRedis(decode_responses=True),
    }
    await reconcile_trials(ctx)

    # The limited user is healed back to claimable and notified; the live user is untouched.
    assert await _status(db_sessions, 1) is UserStatus.available
    assert await _status(db_sessions, 2) is UserStatus.active_config
    assert bot.sent == [1]


async def test_reconcile_is_idempotent(db_sessions) -> None:
    await _add(db_sessions, 1, "g1")
    bot = FakeBot()
    ctx = {
        "sessionmaker": db_sessions,
        "panel": FakePanel({"g1": "LIMITED"}),
        "bot": bot,
        "cache_redis": fakeredis.aioredis.FakeRedis(decode_responses=True),
    }
    await reconcile_trials(ctx)
    await reconcile_trials(ctx)  # second sweep: user already reset → not re-notified

    assert bot.sent == [1]
    assert await _status(db_sessions, 1) is UserStatus.available


async def test_reconcile_skips_user_disabled_reminders(db_sessions) -> None:
    async with db_sessions() as session:
        session.add(
            User(
                telegram_id=3,
                status=UserStatus.active_config,
                panel_username="g3",
                reminder_enabled=False,
            )
        )
        await session.commit()

    bot = FakeBot()
    ctx = {
        "sessionmaker": db_sessions,
        "panel": FakePanel({"g3": "LIMITED"}),
        "bot": bot,
        "cache_redis": fakeredis.aioredis.FakeRedis(decode_responses=True),
    }
    await reconcile_trials(ctx)

    # Still reset (so they can claim again), but no message when reminders are off.
    assert await _status(db_sessions, 3) is UserStatus.available
    assert bot.sent == []
