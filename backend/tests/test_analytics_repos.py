"""Phase B analytics repository methods (bot side), verified against a real Postgres schema."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from gozar.db.models.config_log import ConfigLog
from gozar.db.models.enums import Language, UserStatus
from gozar.db.models.user import User
from gozar.db.repositories.config_log import ConfigLogRepository
from gozar.db.repositories.user import UserRepository


async def _seed(session) -> datetime:
    now = datetime.now(UTC)
    session.add_all(
        [
            User(telegram_id=1, created_at=now - timedelta(days=40)),
            User(telegram_id=2, created_at=now - timedelta(days=6)),
            User(telegram_id=3, created_at=now - timedelta(days=2), referred_by=1),
            User(telegram_id=4, created_at=now - timedelta(days=2), referred_by=1),  # never claims
            User(telegram_id=5, created_at=now - timedelta(hours=1), reminder_enabled=False),
        ]
    )
    await session.flush()
    session.add_all(
        [
            # u1: first claim 1h after signup (within 24h), plus a recent claim today
            ConfigLog(
                user_id=1, location="DE", created_at=now - timedelta(days=40) + timedelta(hours=1)
            ),
            ConfigLog(user_id=1, location="DE", created_at=now - timedelta(hours=2)),
            # u2: first claim 30h after signup (NOT within 24h), 4 days ago
            ConfigLog(
                user_id=2, location="NL", created_at=now - timedelta(days=6) + timedelta(hours=30)
            ),
            # u3: first claim 10h after signup (within 24h), 2 days ago
            ConfigLog(
                user_id=3, location="DE", created_at=now - timedelta(days=2) + timedelta(hours=10)
            ),
        ]
    )
    await session.commit()
    return now


async def test_active_user_counts(session):
    now = await _seed(session)
    logs = ConfigLogRepository(session)
    assert await logs.active_user_count_since(now - timedelta(days=1)) == 1  # DAU: only u1's recent
    assert await logs.active_user_count_since(now - timedelta(days=7)) == 3  # WAU: u1, u2, u3
    assert (
        await logs.active_user_count_since(now - timedelta(days=30)) == 3
    )  # MAU (40d claim excluded)


async def test_claims_per_user_buckets(session):
    await _seed(session)
    buckets = await ConfigLogRepository(session).claims_per_user_buckets()
    assert buckets == {"1": 2, "2-3": 1}  # u1 has 2, u2 & u3 have 1 each


async def test_first_claim_stats(session):
    await _seed(session)
    median, within_24h, total = await ConfigLogRepository(session).first_claim_stats()
    assert total == 3
    assert within_24h == 2  # u1 (1h) and u3 (10h)
    assert median == 10.0  # median of [1, 10, 30]


async def test_hourly_weekday_counts_sum(session):
    now = await _seed(session)
    cells = await ConfigLogRepository(session).hourly_weekday_counts(now - timedelta(days=7))
    assert sum(n for _, _, n in cells) == 3  # three claims fall in the 7-day window
    assert all(0 <= dow <= 6 and 0 <= hour <= 23 for dow, hour, _ in cells)


async def test_referral_funnel(session):
    await _seed(session)
    joined, claimed, eligible = await UserRepository(session).referral_funnel()
    assert joined == 2  # u3, u4 have referred_by set
    assert claimed == 1  # of those, only u3 ever claimed
    # The denominator is everyone who signed up at or after the FIRST referral, not everyone.
    # u1 (40 days ago) and u2 (6 days ago) predate u3/u4 (2 days ago), so only u3, u4 and u5
    # could have arrived via an invite. Measured against all five the share would be 40%; against
    # the three who could have been referred it is 67%, which is the figure that can move.
    assert eligible == 3


async def test_referral_denominator_excludes_the_era_before_referrals(session):
    """On the live install `referred_by` is NULL for every legacy-imported row, so dividing by all
    users reported 10.8% where the honest figure was 17.0% — the axis was measuring how much of the
    service predates the feature rather than how well the feature works."""
    now = datetime.now(UTC)
    session.add_all(
        [
            # Five users from before the referral programme existed. None can have a referrer.
            *[User(telegram_id=100 + i, created_at=now - timedelta(days=90)) for i in range(5)],
            User(telegram_id=200, created_at=now - timedelta(days=1)),
            User(telegram_id=201, created_at=now - timedelta(days=1), referred_by=200),
        ]
    )
    await session.flush()

    joined, _claimed, eligible = await UserRepository(session).referral_funnel()
    assert joined == 1
    # Only the two users from the referral era, not all seven.
    assert eligible == 2


async def test_referral_denominator_is_zero_before_any_referral(session):
    """With no referrals recorded there is no cutoff, so the count is 0 — which the route turns
    into a 0% share rather than dividing by zero."""
    session.add(User(telegram_id=300))
    await session.flush()
    joined, _claimed, eligible = await UserRepository(session).referral_funnel()
    assert (joined, eligible) == (0, 0)


async def test_reminder_by_language(session):
    await _seed(session)
    rows = dict(
        (lang, (on, off)) for lang, on, off in await UserRepository(session).reminder_by_language()
    )
    # all users default to fa; u5 has reminders off
    assert rows[Language.fa.value] == (4, 1)


async def test_active_user_count_empty(session):
    # empty DB: no crash, zero everywhere
    logs = ConfigLogRepository(session)
    assert await logs.active_user_count_since(datetime.now(UTC) - timedelta(days=7)) == 0
    assert await logs.claims_per_user_buckets() == {}
    assert await logs.first_claim_stats() == (None, 0, 0)
    _ = UserStatus  # keep import used for parity with other test modules
