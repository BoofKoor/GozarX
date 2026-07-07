"""add users.last_claim_at (rolling-cooldown anchor)

Revision ID: b8e4c2f5a611
Revises: 43fa64c4458a
Create Date: 2026-07-07 12:00:00.000000

The rolling claim cooldown was keyed off the latest ``config_logs`` row, whose ``created_at`` is the
LOCATION-PICK time — a few moments AFTER ``claim()`` provisions the panel account (whose ``expireAt``
is set at that earlier instant). So the cooldown ended slightly after the trial actually expired, and
the "your trial expired, grab a fresh one now" reminder could land a hair before a re-claim was
allowed. ``last_claim_at`` records the provision instant itself, so the cooldown lines up with the
trial's own expiry (both = claim + trial_hours).

Backfill it from each user's latest ``config_logs.created_at`` so existing users keep their current
cooldown (no one is freed early or blocked longer by the switch); fresh claims set it precisely.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "b8e4c2f5a611"
down_revision: str | None = "43fa64c4458a"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("users", sa.Column("last_claim_at", sa.DateTime(timezone=True), nullable=True))
    # Preserve the existing cooldown: seed from the newest delivered-config time per user.
    op.execute(
        sa.text(
            "UPDATE users SET last_claim_at = ("
            "  SELECT max(created_at) FROM config_logs WHERE config_logs.user_id = users.telegram_id"
            ")"
        )
    )


def downgrade() -> None:
    op.drop_column("users", "last_claim_at")
