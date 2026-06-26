"""wrap config_delivered link in <code> for HTML parse_mode

Revision ID: a7c3f1e9b204
Revises: 3574f69301be
Create Date: 2026-06-26 18:00:00.000000

Phase 2 seeded ``config_delivered`` with a Markdown backtick around ``{link}``, but the bot sends
with HTML parse_mode (Phase 3), where backticks are literal. The non-clobbering seed can't fix an
already-inserted row, so this migration rewrites just the ``{link}`` wrapping (```{link}```
-> ``<code>{link}</code>``) for every language. It is surgical (touches only the wrapping, preserving
any surrounding admin edits) and idempotent (rows already using ``<code>`` are skipped).
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "a7c3f1e9b204"
down_revision: str | None = "3574f69301be"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_BACKTICK = "`{link}`"
_CODE = "<code>{link}</code>"


def upgrade() -> None:
    op.execute(
        sa.text(
            "UPDATE content SET body = replace(body, :old, :new) "
            "WHERE key = 'config_delivered' AND body LIKE :pat"
        ).bindparams(old=_BACKTICK, new=_CODE, pat=f"%{_BACKTICK}%")
    )


def downgrade() -> None:
    op.execute(
        sa.text(
            "UPDATE content SET body = replace(body, :old, :new) "
            "WHERE key = 'config_delivered' AND body LIKE :pat"
        ).bindparams(old=_CODE, new=_BACKTICK, pat=f"%{_CODE}%")
    )
