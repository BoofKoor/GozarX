"""site_device_days — a visit recorded per device per local day

Revision ID: e4b8c2d6f1a3
Revises: d1e5a7c3b9f0
Create Date: 2026-09-30

``site_devices.last_seen_at`` is overwritten on each visit, so a past window could only count the
devices that never came back after it. This table records the day itself. It is NOT backfilled:
``last_seen_at`` holds one day per device, and seeding from it would reproduce the very undercount
this exists to end while hiding where the real record starts. The stats endpoint reports the first
recorded instant instead, and says "not recorded yet" for anything before it.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision: str = "e4b8c2d6f1a3"
down_revision: str | None = "d1e5a7c3b9f0"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    op.create_table(
        "site_device_days",
        sa.Column("device_uuid", sa.String(length=36), nullable=False),
        sa.Column("day", sa.Date(), nullable=False),
        sa.Column("first_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["device_uuid"], ["site_devices.uuid"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("device_uuid", "day"),
    )
    op.create_index("ix_site_device_days_first_at", "site_device_days", ["first_at"])


def downgrade() -> None:
    op.drop_index("ix_site_device_days_first_at", table_name="site_device_days")
    op.drop_table("site_device_days")
