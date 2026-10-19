"""ops tables — saved servers, the bot's own SSH key, and the console's operation jobs

Phase 30 gives the Telegram console SSH: turning a server into a Remnawave node, connecting the
panel's existing nodes to the bot. Three tables (``gozar/db/models/ops.py`` says why each column is
there):

* ``ops_servers`` — every server the bot logged into once, its host key pinned, no password kept;
* ``ops_keys``    — the bot's own SSH key pair, the private half sealed with VAULT_KEY;
* ``ops_jobs``    — one row per SSH job, written at enqueue time and completed by the worker.

Revision ID: 8d4f2b6e1a93
Revises: 7c3e9a1d5f20
Create Date: 2026-10-19
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "8d4f2b6e1a93"
down_revision: str | None = "7c3e9a1d5f20"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    op.create_table(
        "ops_servers",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("label", sa.String(length=64), nullable=False),
        sa.Column("host", sa.String(length=255), nullable=False),
        sa.Column("port", sa.Integer(), server_default=sa.text("22"), nullable=False),
        sa.Column("username", sa.String(length=64), server_default="root", nullable=False),
        sa.Column("ip", sa.String(length=64), server_default="", nullable=False),
        sa.Column("country", sa.String(length=2), server_default="XX", nullable=False),
        sa.Column("os", sa.String(length=128), server_default="", nullable=False),
        sa.Column("host_key", sa.Text(), nullable=True),
        sa.Column("key_ok", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("sudo_password", sa.Text(), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False
        ),
        sa.Column("last_login_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("label"),
        sa.UniqueConstraint("host", "port", "username", name="uq_ops_servers_login"),
    )
    op.create_table(
        "ops_keys",
        sa.Column("name", sa.String(length=32), nullable=False),
        sa.Column("private", sa.Text(), nullable=False),
        sa.Column("public", sa.Text(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False
        ),
        sa.PrimaryKeyConstraint("name"),
    )
    op.create_table(
        "ops_jobs",
        sa.Column("id", sa.String(length=32), nullable=False),
        sa.Column("kind", sa.String(length=32), nullable=False),
        sa.Column("status", sa.String(length=16), server_default="queued", nullable=False),
        sa.Column("chat_id", sa.BigInteger(), nullable=False),
        sa.Column("message_id", sa.Integer(), nullable=True),
        sa.Column("lang", sa.String(length=2), server_default="fa", nullable=False),
        sa.Column(
            "params",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column("result", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("created_by", sa.BigInteger(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False
        ),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_ops_jobs_created_at", "ops_jobs", [sa.text("created_at DESC")])


def downgrade() -> None:
    op.drop_index("ix_ops_jobs_created_at", table_name="ops_jobs")
    op.drop_table("ops_jobs")
    op.drop_table("ops_keys")
    op.drop_table("ops_servers")
