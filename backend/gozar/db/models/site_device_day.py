"""``site_device_days`` — one row per device per LOCAL day it was seen.

``site_devices.last_seen_at`` is overwritten on every visit, so it can only answer "seen since X":
a device that came every day of the previous week and again today had left no trace in that week.
Counting a PAST window from it counted only the devices that never came back, and the daily visitor
series put each device on its last day alone — 1,000 loyal daily visitors read as 0 last week and a
cliff today. Recording the day itself is the only way a past window can be counted.

``first_at`` is the device's first request of that day, which is what lets a window that ENDS
mid-day (the previous period of a range that runs to "now") be counted exactly: a day row counts
when the device was already seen before the window's end.
"""

from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import Date, DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from gozar.db.base import Base


class SiteDeviceDay(Base):
    __tablename__ = "site_device_days"

    device_uuid: Mapped[str] = mapped_column(
        String(36), ForeignKey("site_devices.uuid", ondelete="CASCADE"), primary_key=True
    )
    #: The local (``DISPLAY_TZ``) calendar day.
    day: Mapped[date] = mapped_column(Date, primary_key=True)
    first_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
