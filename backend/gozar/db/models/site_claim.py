"""``site_claims`` table — one row per website trial-config claim (the site's ``config_logs``).

``location`` is the remark NAME the config was matched to (never a list index — the v1 bug), written
at location-pick time. FK to ``site_devices`` (CASCADE), never to the bot ``users`` table.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import BigInteger, Boolean, DateTime, ForeignKey, String, func, text
from sqlalchemy.orm import Mapped, mapped_column

from gozar.db.base import Base


class SiteClaim(Base):
    __tablename__ = "site_claims"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    device_uuid: Mapped[str] = mapped_column(
        String(36), ForeignKey("site_devices.uuid", ondelete="CASCADE"), index=True
    )
    # Location remark NAME (configs are matched to locations by name, never by index).
    location: Mapped[str] = mapped_column(String(128))
    # True when this delivery was a change-location (re-pick on an existing trial), False for the
    # provision that opened the trial. The site logs a row for EVERY delivery (history + current-
    # location depend on it), so the admin funnel stats (configs/day, top locations) filter to
    # provisions — matching the bot, whose config_logs only records the claim. Without this a heavy
    # location-switcher would inflate every site funnel number.
    is_change: Mapped[bool] = mapped_column(Boolean, default=False, server_default=text("false"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
