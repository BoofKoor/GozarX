"""``broadcast_logs`` table — one row per admin-composed Telegram broadcast.

The panel's send runs in the arq worker, never in the request, so the HTTP response can only ever
say "queued". Without a row the operator pressed send and then had no way to learn what happened:
how many it reached, how many were unreachable, how many users were removed — or whether the worker
was running at all. The bot's own ``/admin`` broadcast reports its progress by editing a Telegram
message, which is fine while you are watching and gone the moment you are not.

The row is written at ENQUEUE time and completed by ``broadcast_text``, so a job that never runs
still shows in the history as stuck on ``queued`` rather than vanishing. Mirrors
``site_push_logs``, deliberately: two broadcast surfaces that report their outcome differently
would be two things to learn.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import BigInteger, Boolean, DateTime, Index, Integer, String, Text, func, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from gozar.db.base import Base


class BroadcastStatus:
    """Lifecycle of a broadcast row (plain strings — no native enum, like ``SitePushStatus``)."""

    queued = "queued"  # enqueued; the worker hasn't picked it up yet
    scheduled = "scheduled"  # enqueued with a deferral — it will start later
    sending = "sending"
    done = "done"
    failed = "failed"  # the worker could not run the fan-out at all


class BroadcastLog(Base):
    __tablename__ = "broadcast_logs"
    # Declared here as well as in the migration so autogenerate SEES it; left out of the model, the
    # next `make migrate` would emit a drop_index for the index the history list depends on.
    __table_args__ = (Index("ix_broadcast_logs_created_at", text("created_at DESC")),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    body: Mapped[str] = mapped_column(Text)
    #: Comma-separated language codes, or "" for everyone. A string rather than an array so the
    #: audience reads the same way in the row, the query and the CSV.
    languages: Mapped[str] = mapped_column(String(32), default="", server_default="")
    only_active: Mapped[bool] = mapped_column(Boolean, default=False, server_default=text("false"))
    only_referrers: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default=text("false")
    )
    #: The inline keyboard as sent: ``[{"text": …, "url": …}, …]``. Stored so the history shows what
    #: actually went out, not what the composer happens to hold now.
    buttons: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    status: Mapped[str] = mapped_column(
        String(16), default=BroadcastStatus.queued, server_default=BroadcastStatus.queued
    )
    #: Audience size measured at enqueue time; the rest are filled in by the worker.
    recipients: Mapped[int] = mapped_column(Integer, default=0, server_default=text("0"))
    sent: Mapped[int] = mapped_column(Integer, default=0, server_default=text("0"))
    failed: Mapped[int] = mapped_column(Integer, default=0, server_default=text("0"))
    #: Users dropped during the fan-out. Its own column, not folded into `failed`, because the rule
    #: behind it matters: a user is removed ONLY on a genuine blocked/deactivated error, never on a
    #: transient one, and that distinction has to be visible to be trusted.
    removed: Mapped[int] = mapped_column(Integer, default=0, server_default=text("0"))
    scheduled_for: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
