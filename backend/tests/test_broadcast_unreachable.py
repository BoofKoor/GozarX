"""A broadcast MARKS a gone chat instead of deleting the user (DB-gated).

The delete cascaded the user's claim history away — every past day's figures shrank after each
send — and orphaned the live panel account, which only the row can map back for expiry cleanup.
"""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import func, select

from gozar.db.models.config_log import ConfigLog
from gozar.db.models.enums import UserStatus
from gozar.db.models.user import User
from gozar.db.repositories.user import UserRepository


async def test_marking_keeps_the_row_and_its_history_and_leaves_the_audience(db_sessions) -> None:
    async with db_sessions() as s:
        s.add_all(
            [
                User(telegram_id=1, status=UserStatus.active_config, panel_username="g1"),
                User(telegram_id=2),
            ]
        )
        await s.flush()
        s.add(ConfigLog(user_id=1, location="Germany"))
        await s.commit()

    async with db_sessions() as s:
        repo = UserRepository(s)
        assert await repo.mark_unreachable([1], datetime.now(UTC)) == 1
        await s.commit()

    async with db_sessions() as s:
        repo = UserRepository(s)
        user = await repo.get(1)
        assert user is not None and user.unreachable_at is not None
        assert user.panel_username == "g1"  # still mappable for the expiry cleanup
        assert await s.scalar(select(func.count()).select_from(ConfigLog)) == 1
        # Out of every audience: they cannot receive, and counting them inflates the pre-flight.
        assert await repo.count_audience() == 1
        assert await repo.audience_ids() == [2]
        assert await repo.list_all_ids() == [2]


async def test_marking_more_ids_than_one_statement_can_bind(db_sessions) -> None:
    # An IN list binds one parameter per id and asyncpg refuses more than 32,767 of them, so a
    # broadcast that found 40,000 gone chats marked none — and failed its log row on the way out.
    async with db_sessions() as s:
        s.add_all([User(telegram_id=7), User(telegram_id=39_999)])
        await s.commit()
    async with db_sessions() as s:
        repo = UserRepository(s)
        assert await repo.mark_unreachable(list(range(1, 40_001)), datetime.now(UTC)) == 2
        await s.commit()
    async with db_sessions() as s:
        assert await UserRepository(s).list_all_ids() == []
