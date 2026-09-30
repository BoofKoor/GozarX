"""``config_logs`` table — one row per trial-config claim."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import BigInteger, DateTime, ForeignKey, Index, String, func
from sqlalchemy.orm import Mapped, mapped_column

from gozar.db.base import Base


class ConfigLog(Base):
    __tablename__ = "config_logs"
    # Per-user lookups (latest claim, claim count, the users-list location filter) as index scans.
    __table_args__ = (Index("ix_config_logs_user_created_id", "user_id", "created_at", "id"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    user_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("users.telegram_id", ondelete="CASCADE"), index=True
    )
    # Location remark NAME (configs are matched to locations by name, never by index).
    location: Mapped[str] = mapped_column(String(128))
    # Indexed: every windowed dashboard figure filters on it.
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True
    )
