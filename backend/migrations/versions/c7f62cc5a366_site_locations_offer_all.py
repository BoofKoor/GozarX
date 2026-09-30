"""site_locations — reset the wizard's snapshot to "all", now that the list is a real filter

Revision ID: c7f62cc5a366
Revises: a7d3e9f1c2b5
Create Date: 2026-09-30

Until the previous release the website IGNORED ``site_locations`` whenever the panel answered: it
offered the squad's live names, and the stored list only stood in during an outage. So the list an
existing install holds is the snapshot its setup wizard wrote — never a filter, never maintained.
That release made the list a real filter (unticking a location finally did something), and in doing
so turned the snapshot into one: every host added to the squad since the wizard vanished from the
site on deploy.

``[]`` means "every host the squad serves, live", which is exactly what the site offered before, so
the row is reset once and from here on holds only what an operator ticks. A subset ticked on the
release in between cannot be told apart from the wizard's snapshot and is reset too. The bot's
``locations`` is left alone: the bot always honoured its list, so that one IS the operator's choice.

The settings cache (5-minute TTL) can serve the old list for up to its TTL after the upgrade.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision: str = "c7f62cc5a366"
down_revision: str | None = "a7d3e9f1c2b5"
branch_labels: str | None = None
depends_on: str | None = None

RESET = sa.text("UPDATE settings SET value = '[]' WHERE key = 'site_locations'")


def upgrade() -> None:
    op.get_bind().execute(RESET)


def downgrade() -> None:
    # The snapshot is not recoverable, and the code before this chain ignored it anyway.
    pass
