"""site_claims.is_change — mark change-location re-picks vs opening provisions

The website logs a ``site_claims`` row for every delivery (claim history + the "current config"
screen depend on it), so change-location re-picks were inflating every admin funnel metric relative
to the bot (whose ``config_logs`` only records the opening claim). This flag lets the funnel stats
filter to provisions. Existing rows default to ``false`` (counted as provisions): historical figures
stay a slight over-count, but every delivery from here is classified correctly.

Revision ID: d3f7a1c9b2e4
Revises: c4d2e8f10a37
Create Date: 2026-07-17 00:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "d3f7a1c9b2e4"
down_revision: str | None = "c4d2e8f10a37"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "site_claims",
        sa.Column("is_change", sa.Boolean(), nullable=False, server_default=sa.text("false")),
    )


def downgrade() -> None:
    op.drop_column("site_claims", "is_change")
