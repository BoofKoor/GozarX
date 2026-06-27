"""button_configs

Revision ID: 6dc8fbdbe182
Revises: a7c3f1e9b204
Create Date: 2026-06-27 00:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "6dc8fbdbe182"
down_revision: str | None = "a7c3f1e9b204"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Admin overrides over the in-code button catalogue (Phase 7c). One row per overridden button
    # key; absence = code default. `labels` is a partial {lang: text} JSONB override.
    op.create_table(
        "button_configs",
        sa.Column("key", sa.String(length=64), nullable=False),
        sa.Column("labels", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("is_visible", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("row_index", sa.Integer(), nullable=True),
        sa.Column("position", sa.Integer(), nullable=True),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("key"),
    )


def downgrade() -> None:
    op.drop_table("button_configs")
