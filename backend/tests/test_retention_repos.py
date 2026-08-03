"""Retention / period-comparison repository methods, verified against a real Postgres schema.

These are the queries behind the dashboard's new "do people come back?" panels, so they are all
exercised against real SQL rather than mocked — `date_trunc('week', …)` and the offset arithmetic
have no meaningful in-Python equivalent to assert on.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from gozar.db.models.config_log import ConfigLog
from gozar.db.models.user import User
from gozar.db.repositories.config_log import ConfigLogRepository
from gozar.db.repositories.user import UserRepository


async def _seed(session) -> datetime:
    """Two users signed up 3 weeks ago; one keeps claiming, one claims only in its signup week.
    A third signs up this week and claims today."""
    now = datetime.now(UTC)
    three_weeks = now - timedelta(weeks=3)
    session.add_all(
        [
            User(telegram_id=1, created_at=three_weeks, referral_count=12),
            User(telegram_id=2, created_at=three_weeks, referral_count=3),
            User(telegram_id=3, created_at=now - timedelta(hours=2)),
        ]
    )
    await session.flush()
    session.add_all(
        [
            # u1 claims in its signup week and again 13 days ago — a returner. The second claim sits
            # squarely inside the "previous 7 days" bucket, so the period-comparison test has a
            # non-zero prior period without landing on a window boundary.
            ConfigLog(user_id=1, location="DE", created_at=three_weeks + timedelta(hours=1)),
            ConfigLog(user_id=1, location="DE", created_at=now - timedelta(days=13)),
            # u2 claims only in its signup week.
            ConfigLog(user_id=2, location="NL", created_at=three_weeks + timedelta(hours=3)),
            # u3 claims today — first ever claim.
            ConfigLog(user_id=3, location="DE", created_at=now - timedelta(minutes=30)),
        ]
    )
    await session.commit()
    return now


async def test_weekly_retention_cohorts(session):
    now = await _seed(session)
    cohorts = await ConfigLogRepository(session).weekly_retention_cohorts(weeks=6)
    by_size = {size: offsets for _, size, offsets in cohorts}

    # The 3-weeks-ago cohort has both users; both claimed at offset 0, only u1 came back later.
    assert 2 in by_size, f"expected a 2-user cohort, got {cohorts}"
    older = by_size[2]
    assert older[0] == 2
    assert sum(v for k, v in older.items() if k > 0) == 1  # only u1 returned

    # This week's cohort is u3, active in its own signup week.
    assert 1 in by_size
    assert by_size[1][0] == 1
    assert now is not None


async def test_weekly_retention_cohorts_empty(session):
    assert await ConfigLogRepository(session).weekly_retention_cohorts() == []


async def test_new_vs_returning_daily(session):
    now = await _seed(session)
    rows = await ConfigLogRepository(session).new_vs_returning_daily(now - timedelta(days=2))
    today = now.date().isoformat()
    per_day = {day: (new, returning) for day, new, returning in rows}
    # u3's only claim is today, so today is its first-ever claim day → counted as NEW.
    assert per_day[today] == (1, 0)


async def test_new_vs_returning_marks_repeat_claimers_as_returning(session):
    now = await _seed(session)
    # A window that starts AFTER u1's first claim must report its later claim as returning, not new
    # — the "first day" is computed over all history, not just the window.
    rows = await ConfigLogRepository(session).new_vs_returning_daily(now - timedelta(weeks=2))
    assert sum(returning for _, _, returning in rows) >= 1


async def test_active_users_daily(session):
    now = await _seed(session)
    rows = await ConfigLogRepository(session).active_users_daily(now - timedelta(days=1))
    assert rows == [(now.date().isoformat(), 1)]  # only u3 claimed in the last day


async def test_period_comparison_counts(session):
    now = await _seed(session)
    logs = ConfigLogRepository(session)
    users = UserRepository(session)

    # This 7-day window holds u3's claim; the 7 days before it hold u1's second claim.
    this_week = await logs.count_between(now - timedelta(days=7), now)
    prev_week = await logs.count_between(now - timedelta(days=14), now - timedelta(days=7))
    assert this_week == 1
    assert prev_week == 1

    assert await logs.active_user_count_between(now - timedelta(days=7), now) == 1
    assert await users.count_created_between(now - timedelta(days=7), now) == 1


async def test_referral_cap_stats(session):
    await _seed(session)
    users = UserRepository(session)
    at_cap, any_referrals = await users.referral_cap_stats(cap=10)
    assert any_referrals == 2  # u1 (12) and u2 (3)
    assert at_cap == 1  # only u1 is at/over the cap

    # A cap of 0 means "no cap configured" — nobody can be at it.
    assert await users.referral_cap_stats(cap=0) == (0, 2)


async def test_signups_hourly_weekday(session):
    now = await _seed(session)
    cells = await UserRepository(session).signups_hourly_weekday(now - timedelta(days=1))
    assert sum(n for _, _, n in cells) == 1  # only u3 signed up in the last day
    assert all(0 <= dow <= 6 and 0 <= hour <= 23 for dow, hour, _ in cells)


async def test_status_breakdown(session):
    await _seed(session)
    rows = dict(await UserRepository(session).status_breakdown())
    assert rows == {"available": 3}
