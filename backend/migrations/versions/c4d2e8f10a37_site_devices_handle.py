"""site_devices.handle — public account handle (GZ-XXXXXX)

Adds a short, human-readable, unique handle per device (the user-facing account id + referral code)
and backfills every existing row with a freshly-generated, collision-checked handle.

Revision ID: c4d2e8f10a37
Revises: 5cf70aa2a938
Create Date: 2026-07-12 02:10:00.000000

"""

import secrets
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "c4d2e8f10a37"
down_revision: str | None = "5cf70aa2a938"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# Kept in sync with gozar.db.handles (the migration stays self-contained — no app imports).
_ALPHABET = "23456789ABCDEFGHJKMNPQRSTVWXYZ"


def _handle() -> str:
    return "GZ-" + "".join(secrets.choice(_ALPHABET) for _ in range(6))


def upgrade() -> None:
    op.add_column("site_devices", sa.Column("handle", sa.String(length=16), nullable=True))

    # Backfill: give every existing device a unique handle before the unique index goes on.
    conn = op.get_bind()
    used: set[str] = {
        row[0]
        for row in conn.execute(
            sa.text("SELECT handle FROM site_devices WHERE handle IS NOT NULL")
        )
    }
    uuids = [
        row[0]
        for row in conn.execute(sa.text("SELECT uuid FROM site_devices WHERE handle IS NULL"))
    ]
    for device_uuid in uuids:
        handle = _handle()
        while handle in used:
            handle = _handle()
        used.add(handle)
        conn.execute(
            sa.text("UPDATE site_devices SET handle = :h WHERE uuid = :u"),
            {"h": handle, "u": device_uuid},
        )

    op.create_index("ix_site_devices_handle", "site_devices", ["handle"], unique=True)


def downgrade() -> None:
    op.drop_index("ix_site_devices_handle", table_name="site_devices")
    op.drop_column("site_devices", "handle")
