"""broadcast_logs — record every panel-composed Telegram broadcast and its outcome

Revision ID: a7d3e5b91c02
Revises: c8e2f04b7193
Create Date: 2026-08-05

The fan-out runs in the arq worker, so the HTTP response can only ever say "queued". Without a row
the operator pressed send and then had no way to learn what happened: how many it reached, how many
were unreachable, how many users were dropped — or whether the worker was running at all. The bot's
own ``/admin`` reports progress by editing a Telegram message, which is fine while you are watching
it and gone the moment you are not.

``removed`` is its own column rather than part of ``failed`` because the rule behind it matters: a
user is dropped ONLY on a genuine blocked/deactivated error, never on a transient one, and that
distinction has to be visible to be trusted.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "a7d3e5b91c02"
down_revision: str | None = "c8e2f04b7193"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    op.create_table(
        "broadcast_logs",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        # Comma-separated language codes; "" = everyone.
        sa.Column("languages", sa.String(length=32), server_default="", nullable=False),
        sa.Column("only_active", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("only_referrers", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        # The inline keyboard as SENT, so the history shows what went out rather than what the
        # composer happens to hold now.
        sa.Column("buttons", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("status", sa.String(length=16), server_default="queued", nullable=False),
        sa.Column("recipients", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("sent", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("failed", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("removed", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("scheduled_for", sa.DateTime(timezone=True), nullable=True),
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
    op.create_index("ix_broadcast_logs_created_at", "broadcast_logs", [sa.text("created_at DESC")])


def downgrade() -> None:
    op.drop_index("ix_broadcast_logs_created_at", table_name="broadcast_logs")
    op.drop_table("broadcast_logs")
