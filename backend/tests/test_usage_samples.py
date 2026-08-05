"""The usage recorder, verified against a real Postgres schema.

The differencing rules are the whole point of this repository — the table stores a cumulative
counter and every figure a chart wants is a difference — so they are what these tests pin.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from gozar.config.reporting import DISPLAY_TZ
from gozar.db.models.usage_sample import UsageSample
from gozar.db.repositories.usage_sample import UsageSampleRepository

GB = 1024**3


def _local_midnight_utc(days_ago: int) -> datetime:
    """UTC instant of local midnight ``days_ago`` days back — the same anchor the routes use."""
    local_today = datetime.now(DISPLAY_TZ).replace(hour=0, minute=0, second=0, microsecond=0)
    return (local_today - timedelta(days=days_ago)).astimezone(UTC)


async def _seed(session, readings: list[tuple[datetime, int, int]]) -> None:
    session.add_all(
        [
            UsageSample(captured_at=at, total_bytes=total, online_now=online)
            for at, total, online in readings
        ]
    )
    await session.flush()


async def test_daily_differences_the_cumulative_counter(session) -> None:
    """A day's traffic is the gap between its LAST reading and the previous day's last — not the
    spread within the day, which would lose everything carried overnight."""
    await _seed(
        session,
        [
            (_local_midnight_utc(2) + timedelta(hours=1), 10 * GB, 5),
            (_local_midnight_utc(2) + timedelta(hours=20), 12 * GB, 9),
            (_local_midnight_utc(1) + timedelta(hours=3), 15 * GB, 4),
            (_local_midnight_utc(1) + timedelta(hours=22), 18 * GB, 11),
        ],
    )
    rows = await UsageSampleRepository(session).daily(_local_midnight_utc(3).date())

    assert len(rows) == 2
    # The first day has no predecessor, so its traffic is structurally unknown — 0, and the route
    # drops it rather than charting a day the service looks idle.
    assert rows[0].bytes == 0
    # 18 GB - 12 GB: the overnight jump from 12→15 belongs to the second day and is included.
    assert rows[1].bytes == 6 * GB
    assert rows[1].peak_online == 11
    assert not any(r.counter_reset for r in rows)


async def test_counter_reset_reads_as_zero_and_is_flagged(session) -> None:
    """A panel restart or a traffic reset drops the lifetime counter. That must not become a
    negative bar, and it must not be silently absorbed either — the day says so."""
    await _seed(
        session,
        [
            (_local_midnight_utc(2) + timedelta(hours=12), 900 * GB, 7),
            (_local_midnight_utc(1) + timedelta(hours=12), 3 * GB, 6),  # counter reset
        ],
    )
    rows = await UsageSampleRepository(session).daily(_local_midnight_utc(3).date())

    assert rows[1].bytes == 0
    assert rows[1].counter_reset is True


async def test_window_traffic_anchors_on_the_reading_before_it(session) -> None:
    """Bytes carried in a window are measured from the last reading BEFORE it, so traffic carried
    between that reading and the window's first sample is not dropped on the floor."""
    repo = UsageSampleRepository(session)
    start = _local_midnight_utc(1)
    await _seed(
        session,
        [
            (start - timedelta(hours=2), 100 * GB, 3),  # before the window
            (start + timedelta(hours=1), 130 * GB, 8),
            (start + timedelta(hours=10), 160 * GB, 12),
        ],
    )
    now = datetime.now(UTC) + timedelta(hours=1)

    # 160 - 100, not 160 - 130: the 30 GB carried across the boundary belongs to this window.
    assert await repo.traffic_between(start, now) == 60 * GB
    assert await repo.peak_online_between(start, now) == 12


async def test_window_with_no_earlier_reading_uses_its_own_first(session) -> None:
    """The very first window has nothing before it. Its own first reading is the only honest
    baseline — anything else would invent traffic from before recording began."""
    repo = UsageSampleRepository(session)
    start = _local_midnight_utc(1)
    await _seed(
        session,
        [
            (start + timedelta(hours=2), 500 * GB, 4),
            (start + timedelta(hours=9), 512 * GB, 6),
        ],
    )
    assert await repo.traffic_between(start, datetime.now(UTC) + timedelta(hours=1)) == 12 * GB


async def test_empty_table_answers_without_pretending(session) -> None:
    """Before the sampler has ever run, every figure is 0 and ``first_captured_at`` is None — which
    is what lets the panel say "not recording yet" instead of "no traffic"."""
    repo = UsageSampleRepository(session)
    now = datetime.now(UTC)
    assert await repo.first_captured_at() is None
    assert await repo.sample_count() == 0
    assert await repo.latest() is None
    assert await repo.traffic_between(now - timedelta(days=7), now) == 0
    assert await repo.daily(_local_midnight_utc(7).date()) == []
