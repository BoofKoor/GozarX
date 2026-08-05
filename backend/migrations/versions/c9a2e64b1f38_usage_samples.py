"""usage_samples — start recording what the service carries, because the panel only reports a total

Revision ID: c9a2e64b1f38
Revises: b4f1c8a72d09
Create Date: 2026-08-05

The panel reports traffic as ``nodes.totalBytesLifetime``: one cumulative counter that only ever
grows. It can answer "how much have we ever carried" and nothing else — last Tuesday is not
derivable from it, and a history nobody wrote down cannot be recovered later. Concurrency is worse:
``onlineNow`` is a live reading with no history at all, and the health sampler's own series lives in
a capped Redis list that a restart erases.

So the series starts here and accrues forward. Readings are stored EXACTLY as the panel gave them,
cumulative counter included, and the daily deltas are taken at read time — which is what keeps a
counter RESET visible (a negative difference) instead of baking it into a stored figure that
silently swallowed it. A panel restart, a node removed and re-added, or an admin running
reset-traffic all do that.

Hourly sampling is ~8,760 rows a year, so no retention policy is needed for a long time.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision: str = "c9a2e64b1f38"
down_revision: str | None = "b4f1c8a72d09"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    op.create_table(
        "usage_samples",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column(
            "captured_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        # Cumulative, never a delta. BigInteger because a lifetime byte counter passes 2^31 at 2 GB.
        sa.Column("total_bytes", sa.BigInteger(), server_default=sa.text("0"), nullable=False),
        sa.Column("online_now", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("nodes_online", sa.Integer(), server_default=sa.text("0"), nullable=False),
        # Panel host memory, so "we are running out of room" is answerable over time rather than
        # only at the instant someone opens the system page.
        sa.Column("mem_used", sa.BigInteger(), server_default=sa.text("0"), nullable=False),
        sa.Column("mem_total", sa.BigInteger(), server_default=sa.text("0"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    # Every read is either "the newest reading" or "a window of readings"; without this each one is
    # a sequential scan that grows with the table.
    op.create_index(
        "ix_usage_samples_captured_at",
        "usage_samples",
        [sa.text("captured_at DESC")],
    )


def downgrade() -> None:
    op.drop_index("ix_usage_samples_captured_at", table_name="usage_samples")
    op.drop_table("usage_samples")
