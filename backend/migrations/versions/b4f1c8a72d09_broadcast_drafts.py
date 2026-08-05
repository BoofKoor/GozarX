"""broadcast_drafts — keep an unsent broadcast so a refresh cannot destroy it

Revision ID: b4f1c8a72d09
Revises: a7d3e5b91c02
Create Date: 2026-08-05

A broadcast is the one thing in the panel that is written rather than configured: a few paragraphs,
in three languages, with the buttons and the audience that belong to them. Until now the only copy
lived in React state, so a refresh, an expired JWT or a closed tab took it.

In the database rather than in the browser because the panel is a SHARED operator console — one
person drafts an announcement, another sends it. A draft in ``localStorage`` is invisible to
everyone but the tab that typed it, gone with a cleared cache, and absent from the phone the same
admin picks up an hour later.

Separate from ``broadcast_logs`` on purpose: a log row records something that happened and is never
edited, a draft is mutable right up until it stops being a draft. One table doing both would make
every history query responsible for remembering to exclude the unsent ones.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "b4f1c8a72d09"
down_revision: str | None = "a7d3e5b91c02"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    op.create_table(
        "broadcast_drafts",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        # Derived from the body on save, so a draft never has to be named before it can be kept.
        sa.Column("title", sa.String(length=120), server_default="", nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        # The same shapes the send route takes, so restoring is an assignment, not a translation.
        sa.Column("languages", sa.String(length=32), server_default="", nullable=False),
        sa.Column("only_active", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("only_referrers", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("buttons", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        # Just the hour: an absolute instant saved on Monday is in the past by Tuesday, and
        # "21:00" is what the operator actually chose.
        sa.Column("send_hour", sa.Integer(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    # The list is always "newest first"; without this it is a sort of the whole table on every open.
    op.create_index(
        "ix_broadcast_drafts_updated_at",
        "broadcast_drafts",
        [sa.text("updated_at DESC")],
    )


def downgrade() -> None:
    op.drop_index("ix_broadcast_drafts_updated_at", table_name="broadcast_drafts")
    op.drop_table("broadcast_drafts")
