"""Unit tests for the shared stat-series helpers (services/stats.py)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from gozar.services.stats import window_start, zero_filled_daily


def _today() -> str:
    return datetime.now(UTC).date().isoformat()


def test_window_start_is_midnight_utc_n_minus_one_days_back() -> None:
    start = window_start(7)
    assert (start.hour, start.minute, start.second, start.microsecond) == (0, 0, 0, 0)
    assert start.tzinfo is UTC
    assert start.date() == datetime.now(UTC).date() - timedelta(days=6)


def test_window_start_clamps_below_one() -> None:
    # days=0/negative must not span into the future; treated as a single-day window ending today.
    assert window_start(0).date() == datetime.now(UTC).date()


def test_zero_filled_daily_returns_exactly_n_ascending_points() -> None:
    since = window_start(14)
    out = zero_filled_daily([], since=since, days=14)
    assert len(out) == 14
    days = [d for d, _ in out]
    assert days == sorted(days)  # ascending
    assert days[0] == since.date().isoformat()
    assert days[-1] == _today()
    assert all(n == 0 for _, n in out)  # empty input → all zeros, no gaps collapsed


def test_zero_filled_daily_keeps_present_days_and_fills_gaps() -> None:
    since = window_start(7)
    today = _today()
    oldest = since.date().isoformat()
    out = dict(zero_filled_daily([(today, 5), (oldest, 2)], since=since, days=7))
    assert out[today] == 5
    assert out[oldest] == 2
    # every interior day is present and zero-filled
    assert len(out) == 7
    assert sum(out.values()) == 7


def test_zero_filled_daily_ignores_rows_outside_the_window() -> None:
    since = window_start(7)
    stale = (since.date() - timedelta(days=3)).isoformat()
    out = dict(zero_filled_daily([(stale, 99)], since=since, days=7))
    assert stale not in out
    assert len(out) == 7
    assert sum(out.values()) == 0
