"""Reporting constants shared by every layer.

Lives in ``config`` (the bottom of the import graph) because both ``services/stats`` and the
``db/repositories`` daily-bucket queries need it, and a repository must never import a service.
"""

from __future__ import annotations

from datetime import date, timedelta
from zoneinfo import ZoneInfo

# The timezone the admin panel reports in. The audience and the operator are both on Iran time, and
# the claims heatmap has always bucketed here — but "today" and the daily series were computed on a
# UTC midnight, so the first 3.5 hours of every local day reported the previous day's numbers.
#
# DISPLAY_TZ_NAME is what SQL passes to `timezone(...)`; DISPLAY_TZ is for Python-side date math.
DISPLAY_TZ_NAME = "Asia/Tehran"
DISPLAY_TZ = ZoneInfo(DISPLAY_TZ_NAME)

#: The local week starts on SATURDAY (شنبه). Retention cohorts were ISO weeks on a UTC clock, so a
#: signup at 02:00 on a Monday, Tehran time, landed in the previous week's cohort, and every
#: cohort's "week" began on a day the operator does not start a week on.
WEEK_START_WEEKDAY = 5  # date.weekday(): Monday = 0 … Saturday = 5


def local_week_start(day: date) -> date:
    """The Saturday that opens ``day``'s local week."""
    return day - timedelta(days=(day.weekday() - WEEK_START_WEEKDAY) % 7)
