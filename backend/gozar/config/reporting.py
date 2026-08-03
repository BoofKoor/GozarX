"""Reporting constants shared by every layer.

Lives in ``config`` (the bottom of the import graph) because both ``services/stats`` and the
``db/repositories`` daily-bucket queries need it, and a repository must never import a service.
"""

from __future__ import annotations

from zoneinfo import ZoneInfo

# The timezone the admin panel reports in. The audience and the operator are both on Iran time, and
# the claims heatmap has always bucketed here — but "today" and the daily series were computed on a
# UTC midnight, so the first 3.5 hours of every local day reported the previous day's numbers.
#
# DISPLAY_TZ_NAME is what SQL passes to `timezone(...)`; DISPLAY_TZ is for Python-side date math.
DISPLAY_TZ_NAME = "Asia/Tehran"
DISPLAY_TZ = ZoneInfo(DISPLAY_TZ_NAME)
