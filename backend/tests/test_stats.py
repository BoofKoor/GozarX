"""Unit tests for the shared stat-series helpers (services/stats.py).

The axis these helpers produce is the OPERATOR'S calendar (Asia/Tehran), not UTC. That distinction
is the whole point of the module: with a UTC midnight, the first 3.5 hours of every Iranian day
reported the previous day's totals and every chart bar straddled two of the operator's days. So the
expectations here are written against local dates — a test that says ``datetime.now(UTC).date()``
would pass for 20.5 hours a day and fail for the other 3.5.
"""

from __future__ import annotations

from datetime import UTC, timedelta

from gozar.services.stats import (
    day_keys,
    local_now,
    previous_window,
    start_of_today,
    window_start,
    zero_filled_daily,
)


def _today() -> str:
    return local_now().date().isoformat()


def test_start_of_today_is_local_midnight_expressed_in_utc() -> None:
    start = start_of_today()
    assert start.tzinfo is UTC  # the query bound is UTC; only the BOUNDARY is local
    local = start.astimezone(local_now().tzinfo)
    assert (local.hour, local.minute, local.second, local.microsecond) == (0, 0, 0, 0)
    assert local.date() == local_now().date()


def test_window_start_is_local_midnight_n_minus_one_days_back() -> None:
    start = window_start(7)
    local = start.astimezone(local_now().tzinfo)
    assert (local.hour, local.minute, local.second, local.microsecond) == (0, 0, 0, 0)
    assert local.date() == local_now().date() - timedelta(days=6)


def test_window_start_clamps_below_one() -> None:
    # days=0/negative must not span into the future; treated as a single-day window ending today.
    assert window_start(0) == start_of_today()


def test_day_keys_are_local_dates_ending_today() -> None:
    keys = day_keys(7)
    assert len(keys) == 7
    assert keys == sorted(keys)
    assert keys[-1] == _today()
    assert keys[0] == (local_now().date() - timedelta(days=6)).isoformat()


def test_previous_window_is_adjacent_and_the_same_length() -> None:
    # A "vs last period" chip is meaningless unless the two windows are equal-length and disjoint.
    start, end = previous_window(7)
    assert end == window_start(7)
    assert end - start == timedelta(days=7)


def test_zero_filled_daily_returns_exactly_n_ascending_points() -> None:
    since = window_start(14)
    out = zero_filled_daily([], since=since, days=14)
    assert len(out) == 14
    days = [d for d, _ in out]
    assert days == sorted(days)  # ascending
    assert days[0] == (local_now().date() - timedelta(days=13)).isoformat()
    assert days[-1] == _today()
    assert all(n == 0 for _, n in out)  # empty input → all zeros, no gaps collapsed


def test_zero_filled_daily_keeps_present_days_and_fills_gaps() -> None:
    keys = day_keys(7)
    today, oldest = keys[-1], keys[0]
    out = dict(zero_filled_daily([(today, 5), (oldest, 2)], since=window_start(7), days=7))
    assert out[today] == 5
    assert out[oldest] == 2
    # every interior day is present and zero-filled
    assert len(out) == 7
    assert sum(out.values()) == 7


def test_zero_filled_daily_ignores_rows_outside_the_window() -> None:
    stale = (local_now().date() - timedelta(days=10)).isoformat()
    out = dict(zero_filled_daily([(stale, 99)], since=window_start(7), days=7))
    assert stale not in out
    assert len(out) == 7
    assert sum(out.values()) == 0
