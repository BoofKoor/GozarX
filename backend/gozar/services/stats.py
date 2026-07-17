"""Shared stat-shaping helpers for the admin dashboard + site-stats routes.

Pure date/series math — no DB, Redis, or panel access — so both the bot dashboard and the website
funnel present identical, correctly-windowed time series. The grouped ``daily_counts`` queries only
return days that actually had rows; charting those directly collapses the time axis (a straight line
drawn across a multi-day gap, or N evenly-spaced bars standing in for a sparse range). These helpers
anchor the window on a UTC day boundary (so the oldest bucket is complete, not a partial slice) and
zero-fill the gaps to exactly ``days`` ascending points ending today.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta


def window_start(days: int) -> datetime:
    """Midnight UTC of the oldest day in an inclusive ``days``-calendar-day window ending today.

    Used as the ``since`` bound for the windowed stat queries. Anchoring on a day boundary (rather
    than ``now - days``) keeps the oldest bucket complete and makes the returned series span exactly
    ``days`` calendar days instead of ``days + 1`` with a partial first bucket.
    """
    today = datetime.now(UTC).replace(hour=0, minute=0, second=0, microsecond=0)
    return today - timedelta(days=max(days, 1) - 1)


def zero_filled_daily(
    rows: list[tuple[str, int]], *, since: datetime, days: int
) -> list[tuple[str, int]]:
    """Densify a sparse ``[(YYYY-MM-DD, count), …]`` grouped-query result into exactly ``days``
    ascending points from ``since``'s day through today, filling absent days with ``0``.

    ``since`` must be the matching :func:`window_start` value so the fill range lines up with the
    query bound. Keeping the axis continuous is what makes the activity/growth charts read honestly.
    """
    counts = dict(rows)
    start = since.date()
    return [
        (day.isoformat(), counts.get(day.isoformat(), 0))
        for day in (start + timedelta(days=d) for d in range(max(days, 1)))
    ]
