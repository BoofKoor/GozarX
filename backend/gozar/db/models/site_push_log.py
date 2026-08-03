"""``site_push_logs`` table — one row per admin-composed Web Push broadcast.

The send itself runs in the arq worker (never in the request), so the HTTP response can only ever
say "queued". Before this table the worker logged its outcome to stderr and nothing else: the admin
pressed send and never learned whether the notification reached anybody, how many subscriptions were
pruned, or whether the worker was even running. The row is created at enqueue time and completed by
``site_push_broadcast``.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import BigInteger, DateTime, Integer, String, Text, func, text
from sqlalchemy.orm import Mapped, mapped_column

from gozar.db.base import Base


class SitePushStatus:
    """Lifecycle of a broadcast row (plain strings — no native enum, like ``SiteDeviceStatus``)."""

    queued = "queued"  # enqueued; the worker hasn't picked it up yet
    sending = "sending"
    done = "done"
    failed = "failed"  # the worker could not run the fan-out at all


class SitePushLog(Base):
    __tablename__ = "site_push_logs"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    title: Mapped[str] = mapped_column(String(120))
    body: Mapped[str] = mapped_column(Text)
    url: Mapped[str] = mapped_column(String(512), default="", server_default="")
    # Target locale, or None for "every active subscription".
    locale: Mapped[str | None] = mapped_column(String(8), nullable=True)
    status: Mapped[str] = mapped_column(
        String(16), default=SitePushStatus.queued, server_default=SitePushStatus.queued
    )
    # Audience size measured at enqueue time; sent/failed/pruned are filled in by the worker.
    recipients: Mapped[int] = mapped_column(Integer, default=0, server_default=text("0"))
    sent: Mapped[int] = mapped_column(Integer, default=0, server_default=text("0"))
    failed: Mapped[int] = mapped_column(Integer, default=0, server_default=text("0"))
    pruned: Mapped[int] = mapped_column(Integer, default=0, server_default=text("0"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
