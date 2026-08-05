"""``usage_samples`` table — a periodic snapshot of what the service is actually carrying.

The panel reports traffic as ``nodes.totalBytesLifetime``: one cumulative counter that only ever
grows. That answers "how much have we ever carried" and nothing else — there is no way to derive
last Tuesday from it, and no way to recover a history that was never written down. Concurrency is
worse: ``onlineStats.onlineNow`` is a live reading with no history at all, and the health sampler
keeps its own series in a capped Redis list that a restart or an eviction erases.

So this table is the recorder. One row per hour, and the series accrues from the moment it ships —
the past is genuinely unrecoverable, and a chart that pretended otherwise would be inventing data.

Every column is stored EXACTLY as the panel reported it, cumulative counter included. The daily
deltas are computed at read time, which keeps one important failure visible: the lifetime counter
can go DOWN — a panel restart, a node removed and re-added, an admin running reset-traffic. Storing
raw and differencing on read means a reset is detectable (``delta < 0``) instead of being baked into
a stored figure that silently swallowed it.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import BigInteger, DateTime, Index, Integer, func, text
from sqlalchemy.orm import Mapped, mapped_column

from gozar.db.base import Base


class UsageSample(Base):
    __tablename__ = "usage_samples"
    # Declared here as well as in the migration so autogenerate SEES it; left out of the model, the
    # next `make migrate` would emit a drop_index for the index every read here depends on.
    __table_args__ = (Index("ix_usage_samples_captured_at", text("captured_at DESC")),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    captured_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    #: ``nodes.totalBytesLifetime`` as read — cumulative, never a delta. BigInteger because a
    #: lifetime byte counter passes 2³¹ at 2 GB.
    total_bytes: Mapped[int] = mapped_column(BigInteger, default=0, server_default=text("0"))
    online_now: Mapped[int] = mapped_column(Integer, default=0, server_default=text("0"))
    nodes_online: Mapped[int] = mapped_column(Integer, default=0, server_default=text("0"))
    #: Panel host memory, so "we are running out of room" is answerable over time rather than only
    #: at the instant someone opens the system page.
    mem_used: Mapped[int] = mapped_column(BigInteger, default=0, server_default=text("0"))
    mem_total: Mapped[int] = mapped_column(BigInteger, default=0, server_default=text("0"))
