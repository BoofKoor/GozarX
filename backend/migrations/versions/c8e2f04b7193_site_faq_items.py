"""site_faq_items — the public site's FAQ, editable from the panel

Revision ID: c8e2f04b7193
Revises: b7d4e15a3c62
Create Date: 2026-08-03

The FAQ was 16 hardcoded strings in the site's bundle, so answering a new recurring question meant
a code change and a redeploy. The seeder fills this table with those same defaults on the next
boot, keyed on (locale, question) — so an existing install gains an editable copy of exactly what
it was already showing.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision: str = "c8e2f04b7193"
down_revision: str | None = "b7d4e15a3c62"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    op.create_table(
        "site_faq_items",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("locale", sa.String(length=8), nullable=False),
        sa.Column("category", sa.String(length=32), nullable=False),
        sa.Column("question", sa.String(length=300), nullable=False),
        sa.Column("answer", sa.Text(), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("published", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        # The seeder's idempotency key: re-running it must not duplicate a default.
        sa.UniqueConstraint("locale", "question", name="uq_site_faq_locale_question"),
    )
    op.create_index("ix_site_faq_items_locale", "site_faq_items", ["locale"])


def downgrade() -> None:
    op.drop_index("ix_site_faq_items_locale", table_name="site_faq_items")
    op.drop_table("site_faq_items")
