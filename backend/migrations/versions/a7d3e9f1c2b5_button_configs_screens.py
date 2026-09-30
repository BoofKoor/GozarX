"""button_configs.screens — order and visibility per screen, not per key

Revision ID: a7d3e9f1c2b5
Revises: f2c6d8a4b1e7
Create Date: 2026-09-30

``change_location`` sits on three screens and ``button_configs`` is keyed by the button alone, so
moving or hiding it on one screen moved or hid it on the other two. Per-screen entries live in a
JSONB map on the same row; the existing columns stay as the fallback for screens without one.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "a7d3e9f1c2b5"
down_revision: str | None = "f2c6d8a4b1e7"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    op.add_column(
        "button_configs",
        sa.Column("screens", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("button_configs", "screens")
