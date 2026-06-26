"""initial schema

Revision ID: 3574f69301be
Revises:
Create Date: 2026-06-26 17:14:40.140879

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "3574f69301be"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


# Native enum types are created/dropped explicitly (once) and referenced from the columns with
# create_type=False, so create_table never re-emits CREATE TYPE (the second table would otherwise
# fail with "type already exists"). Each call returns a fresh instance to avoid sharing a single
# type object across multiple ephemeral tables. We use postgresql.ENUM (not sa.Enum) because only
# the dialect type honors create_type=False.
def _user_status() -> postgresql.ENUM:
    return postgresql.ENUM(
        "available", "active_config", "banned", name="user_status", create_type=False
    )


def _language() -> postgresql.ENUM:
    return postgresql.ENUM("fa", "en", "ru", name="language", create_type=False)


def upgrade() -> None:
    bind = op.get_bind()
    _user_status().create(bind, checkfirst=True)
    _language().create(bind, checkfirst=True)

    op.create_table(
        "content",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("key", sa.String(length=128), nullable=False),
        sa.Column("language", _language(), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("key", "language", name="uq_content_key_language"),
    )
    op.create_table(
        "settings",
        sa.Column("key", sa.String(length=64), nullable=False),
        sa.Column("value", sa.Text(), nullable=False),
        sa.PrimaryKeyConstraint("key"),
    )
    op.create_table(
        "users",
        sa.Column("telegram_id", sa.BigInteger(), autoincrement=False, nullable=False),
        sa.Column("status", _user_status(), server_default="available", nullable=False),
        sa.Column("language", _language(), server_default="fa", nullable=False),
        sa.Column("referral_count", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("panel_username", sa.String(length=64), nullable=True),
        sa.Column(
            "reminder_enabled", sa.Boolean(), server_default=sa.text("true"), nullable=False
        ),
        sa.Column("referred_by", sa.BigInteger(), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False
        ),
        sa.PrimaryKeyConstraint("telegram_id"),
    )
    op.create_index(op.f("ix_users_referred_by"), "users", ["referred_by"], unique=False)
    op.create_table(
        "config_logs",
        sa.Column("id", sa.BigInteger(), nullable=False),
        sa.Column("user_id", sa.BigInteger(), nullable=False),
        sa.Column("location", sa.String(length=128), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.telegram_id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_config_logs_user_id"), "config_logs", ["user_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_config_logs_user_id"), table_name="config_logs")
    op.drop_table("config_logs")
    op.drop_index(op.f("ix_users_referred_by"), table_name="users")
    op.drop_table("users")
    op.drop_table("settings")
    op.drop_table("content")

    bind = op.get_bind()
    _user_status().drop(bind, checkfirst=True)
    _language().drop(bind, checkfirst=True)
