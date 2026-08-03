"""site_devices.last_seen_at — a real visit signal for the website stats

Revision ID: b7d4e15a3c62
Revises: f1a6b3c92d47
Create Date: 2026-08-03

Every website figure was derived from claims plus an all-time "identities minted" counter. That
counter is not a visit count: a client that doesn't keep cookies (crawlers, incognito reloads, most
scripted fetchers) mints a NEW row on every request, so it only grows and drags the conversion rate
down with it. `last_seen_at` gives the panel an honest "visited in this window" figure.

Backfilled from the row's own history so the column isn't blank for existing devices.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision: str = "b7d4e15a3c62"
down_revision: str | None = "f1a6b3c92d47"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    op.add_column(
        "site_devices",
        sa.Column(
            "last_seen_at",
            sa.DateTime(timezone=True),
            nullable=True,
            # Every new row starts "seen now", so the visitor windows never have to treat NULL as a
            # special case. Kept nullable because the column is added to a live table.
            server_default=sa.func.now(),
        ),
    )
    # Best available history for rows that predate the column: the later of "first seen" and "last
    # claimed". Not a real visit time, but it keeps an existing install's windows from reading empty.
    op.execute(
        "UPDATE site_devices SET last_seen_at = GREATEST(created_at, COALESCE(last_claim_at, created_at))"
    )
    op.create_index("ix_site_devices_last_seen_at", "site_devices", ["last_seen_at"])


def downgrade() -> None:
    op.drop_index("ix_site_devices_last_seen_at", table_name="site_devices")
    op.drop_column("site_devices", "last_seen_at")
