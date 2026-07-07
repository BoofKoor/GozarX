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
from gozar.remnawave.schemas import PanelUser, UserTraffic
from gozar.worker.tasks import reconcile_trials


def _panel_user(status: str) -> PanelUser:
    expires = (datetime.now(UTC) + timedelta(hours=12)).isoformat()
    return PanelUser(
        uuid="u",
        username="g",
        status=status,
        expire_at=expires,
        traffic_limit_bytes=1024**3,
        traffic=UserTraffic(used_bytes=1024**3),
    )


class FakePanel:
    """Maps a panel username to its current panel-user status (probed via ``get_user``).

    ``None`` in the map models a 404 — the account was already deleted in the panel (still a
    terminal state for the reconcile: the ``active_config`` Gozar user gets reset)."""

    def __init__(self, by_username: dict[str, str | None]) -> None:
        self._by_username = by_username
        self.probed: list[str] = []
        self.deleted: list[str] = []

    async def get_user(self, username: str) -> PanelUser | None:
        self.probed.append(username)
        status = self._by_username[username]
        return _panel_user(status) if status is not None else None

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
    await _add(db_sessions, 1, "g1")  # time expired
    await _add(db_sessions, 2, "g2")  # still live

    bot = FakeBot()
    panel = FakePanel({"g1": "EXPIRED", "g2": "ACTIVE"})
    ctx = {
        "sessionmaker": db_sessions,
        "panel": panel,
        "bot": bot,
        "cache_redis": fakeredis.aioredis.FakeRedis(decode_responses=True),
    }
    await reconcile_trials(ctx)

    # The expired user is healed to claimable, notified, and deleted; the live user is untouched.
    assert await _status(db_sessions, 1) is UserStatus.available
    assert await _status(db_sessions, 2) is UserStatus.active_config
    assert bot.sent == [1]
    assert panel.deleted == ["g1"]


async def test_reconcile_skips_data_limited_but_time_valid(db_sessions) -> None:
    # DATA ran out but TIME is still valid: the sweep leaves the trial ALONE (kept active_config,
    # not deleted, not notified) — it's revivable via a referral bump; only the webhook nudges it.
    await _add(db_sessions, 1, "g1")

    bot = FakeBot()
    panel = FakePanel({"g1": "LIMITED"})  # _panel_user gives a future expireAt -> non-terminal
    ctx = {
        "sessionmaker": db_sessions,
        "panel": panel,
        "bot": bot,
        "cache_redis": fakeredis.aioredis.FakeRedis(decode_responses=True),
    }
    await reconcile_trials(ctx)

    assert await _status(db_sessions, 1) is UserStatus.active_config  # left live
    assert bot.sent == []  # no reminder from the sweep
    assert panel.deleted == []  # account kept


async def test_reconcile_is_idempotent(db_sessions) -> None:
    await _add(db_sessions, 1, "g1")
    bot = FakeBot()
    ctx = {
        "sessionmaker": db_sessions,
        "panel": FakePanel({"g1": "EXPIRED"}),
        "bot": bot,
        "cache_redis": fakeredis.aioredis.FakeRedis(decode_responses=True),
    }
    await reconcile_trials(ctx)
    await reconcile_trials(ctx)  # second sweep: user already reset → not re-notified

    assert bot.sent == [1]
    assert await _status(db_sessions, 1) is UserStatus.available


async def test_reconcile_resets_user_whose_panel_account_is_gone(db_sessions) -> None:
    # get_user 404s (panel account already deleted — e.g. by a prior webhook or manually), yet the
    # Gozar user is still active_config. That's terminal too: reset them so they can claim again.
    await _add(db_sessions, 1, "g1")

    bot = FakeBot()
    panel = FakePanel({"g1": None})  # None -> get_user returns None (404)
    ctx = {
        "sessionmaker": db_sessions,
        "panel": panel,
        "bot": bot,
        "cache_redis": fakeredis.aioredis.FakeRedis(decode_responses=True),
    }
    await reconcile_trials(ctx)

    assert await _status(db_sessions, 1) is UserStatus.available  # healed to claimable
    assert bot.sent == [1]  # expiry reminder still sent


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
        "panel": FakePanel({"g3": "EXPIRED"}),
        "bot": bot,
        "cache_redis": fakeredis.aioredis.FakeRedis(decode_responses=True),
    }
    await reconcile_trials(ctx)

    # Still reset (so they can claim again), but no message when reminders are off.
    assert await _status(db_sessions, 3) is UserStatus.available
    assert bot.sent == []
