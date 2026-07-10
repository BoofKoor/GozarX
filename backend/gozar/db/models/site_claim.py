"""``site_claims`` table — one row per website trial-config claim (the site's ``config_logs``).

``location`` is the remark NAME the config was matched to (never a list index — the v1 bug), written
at location-pick time. FK to ``site_devices`` (CASCADE), never to the bot ``users`` table.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import BigInteger, DateTime, ForeignKey, String, func
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
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
