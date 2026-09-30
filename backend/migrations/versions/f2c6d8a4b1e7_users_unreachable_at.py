"""users.unreachable_at — a broadcast marks a gone chat instead of deleting the user

Revision ID: f2c6d8a4b1e7
Revises: e4b8c2d6f1a3
Create Date: 2026-09-30

A send that Telegram answers with "bot blocked" / "user deactivated" used to delete the user row.
``config_logs`` cascade on that delete, so every broadcast shrank the dashboard's past days, cohorts
and active-user counts; and the user's live panel account lost the only row that maps it back, so
neither the expiry webhook nor the reconcile sweep could ever delete it. The row now stays, marked.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision: str = "f2c6d8a4b1e7"
down_revision: str | None = "e4b8c2d6f1a3"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    op.add_column("users", sa.Column("unreachable_at", sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    op.drop_column("users", "unreachable_at")
