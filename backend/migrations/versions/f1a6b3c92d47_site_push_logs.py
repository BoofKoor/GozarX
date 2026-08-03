"""site_push_logs — record every website Web Push broadcast and its outcome

Revision ID: f1a6b3c92d47
Revises: 4a1e7c9d2f80
Create Date: 2026-08-03

The fan-out runs in the arq worker, so the HTTP response can only say "queued". Without a row the
admin pressed send and never learned whether anything was delivered, how many dead subscriptions
were pruned, or whether the worker was running at all.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision: str = "f1a6b3c92d47"
down_revision: str | None = "4a1e7c9d2f80"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    op.create_table(
        "site_push_logs",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("title", sa.String(length=120), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("url", sa.String(length=512), server_default="", nullable=False),
        # NULL = every active subscription (no locale targeting).
        sa.Column("locale", sa.String(length=8), nullable=True),
        sa.Column("status", sa.String(length=16), server_default="queued", nullable=False),
        sa.Column("recipients", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("sent", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("failed", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("pruned", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    # The history list is always "newest first", so index the exact ordering it pages by.
    op.create_index(
        "ix_site_push_logs_created_at", "site_push_logs", [sa.text("created_at DESC")]
    )


def downgrade() -> None:
    op.drop_index("ix_site_push_logs_created_at", table_name="site_push_logs")
    op.drop_table("site_push_logs")
