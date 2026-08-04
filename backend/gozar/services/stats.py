"""Shared stat-shaping helpers for the admin dashboard + site-stats routes.

Pure date/series math — no DB, Redis, or panel access — so both the bot dashboard and the website
funnel present identical, correctly-windowed time series. The grouped ``daily_counts`` queries only
return days that actually had rows; charting those directly collapses the time axis (a straight line
drawn across a multi-day gap, or N evenly-spaced bars standing in for a sparse range). These helpers
anchor the window on a day boundary (so the oldest bucket is complete, not a partial slice) and
zero-fill the gaps to exactly ``days`` ascending points ending today.

**Days are LOCAL days, not UTC days.** The audience and the operator are both on Iran time, and the
claims heatmap already reported in ``Asia/Tehran`` — but "today" and the daily buckets were computed
on a UTC midnight, so between 00:00 and 03:30 local "دریافت امروز" still showed yesterday's total
and every bar on the chart straddled two of the operator's days. Only DISPLAY metrics use this; the
claim cooldown is a rolling window and is deliberately untouched.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from gozar.config.reporting import DISPLAY_TZ


def local_now() -> datetime:
    return datetime.now(DISPLAY_TZ)


def start_of_today() -> datetime:
    """The UTC instant at which the operator's calendar day began.

    Backs the "today" counters. On UTC midnight they rolled over 3.5 hours early relative to the
    operator's clock, so the first hours of every Iranian day reported the previous day's numbers.
    """
    return local_now().replace(hour=0, minute=0, second=0, microsecond=0).astimezone(UTC)


def window_start(days: int) -> datetime:
    """UTC instant of local midnight on the oldest day of an inclusive ``days``-day window.

    Used as the ``since`` bound for the windowed stat queries. Anchoring on a day boundary (rather
    than ``now - days``) keeps the oldest bucket complete and makes the returned series span exactly
    ``days`` calendar days instead of ``days + 1`` with a partial first bucket.
    """
    return start_of_today() - timedelta(days=max(days, 1) - 1)


def day_keys(days: int) -> list[str]:
    """The window's LOCAL calendar days as ``YYYY-MM-DD``, oldest first.

    The series axis. Generated from the local date rather than from the UTC ``since`` instant —
    which, being 3.5 hours behind local midnight, names the previous day.
    """
    today = local_now().date()
    return [(today - timedelta(days=n)).isoformat() for n in range(max(days, 1) - 1, -1, -1)]


def zero_filled_daily(
    rows: list[tuple[str, int]], *, since: datetime, days: int
) -> list[tuple[str, int]]:
    """Densify a sparse ``[(YYYY-MM-DD, count), …]`` grouped-query result into exactly ``days``
    ascending points ending today, filling absent days with ``0``.

    The row keys must be LOCAL dates (the repositories bucket with ``date(timezone(tz, …))``), which
    is what ``day_keys`` generates. ``since`` is accepted for call-site symmetry with the query
    bound and is not otherwise used. Keeping the axis continuous is what makes the charts read
    honestly.
    """
    counts = dict(rows)
    return [(day, counts.get(day, 0)) for day in day_keys(days)]


def zero_filled_daily_pairs(
    rows: list[tuple[str, int, int]], *, since: datetime, days: int
) -> list[tuple[str, int, int]]:
    """:func:`zero_filled_daily` for a two-value series (e.g. new vs returning claimers per day)."""
    counts = {day: (a, b) for day, a, b in rows}
    return [(day, *counts.get(day, (0, 0))) for day in day_keys(days)]


def previous_window(days: int) -> tuple[datetime, datetime]:
    """``(start, end)`` of the window immediately BEFORE the current ``days``-day one.

    The comparison period must be exactly as long as the current one and must not overlap it, or a
    "+30% vs last period" chip is meaningless. ``end`` is the current window's start, so the two are
    adjacent half-open ranges.
    """
    current_start = window_start(days)
    return current_start - timedelta(days=max(days, 1)), current_start


def pct_change(current: float | None, previous: float | None) -> float | None:
    """Percent change vs the prior period, or ``None`` when there's no baseline to compare against.

    ``None`` (not ``0.0``) on a zero baseline matters: a launch period with real activity would
    otherwise render as "0% — flat". The frontend shows a "new" badge for ``None`` instead.

    ``None`` on either side is also no comparison: a median over an empty cohort is absent, not
    zero, and treating it as zero would report a 100% swing out of nothing.
    """
    if current is None or previous is None or previous <= 0:
        return None
    return round((current - previous) / previous * 100, 1)
