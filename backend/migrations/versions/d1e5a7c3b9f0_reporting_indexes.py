"""reporting indexes — the windowed dashboard and website queries stop scanning whole tables

Revision ID: d1e5a7c3b9f0
Revises: c9a2e64b1f38
Create Date: 2026-09-30

Every windowed figure on the dashboard and the website stats page filters on ``created_at``, and
neither ``config_logs`` nor ``users`` (nor the site's tables) had an index on it, so a 7-day count
read every claim ever made. ``config_logs (user_id, created_at, id)`` serves the per-user lookups —
a user's latest claim (``id`` is the tie-break for two claims in the same microsecond), their claim
count, the users-list location filter — as index scans.

The site's panel-username lookup runs on EVERY expired/limited panel webhook (bot users included,
since the webhook cannot tell the two apart before looking), and the active-device sweep filters on
status; both were sequential scans over a table that gains a row per cookieless visitor.

Plain (not CONCURRENT) builds: they run in the entrypoint before the app serves traffic, and at the
live install's size each takes seconds.
"""

from __future__ import annotations

from alembic import op

revision: str = "d1e5a7c3b9f0"
down_revision: str | None = "c9a2e64b1f38"
branch_labels: str | None = None
depends_on: str | None = None

_INDEXES: list[tuple[str, str, list]] = [
    ("ix_config_logs_created_at", "config_logs", ["created_at"]),
    ("ix_config_logs_user_created_id", "config_logs", ["user_id", "created_at", "id"]),
    ("ix_users_created_at", "users", ["created_at"]),
    ("ix_site_claims_created_at", "site_claims", ["created_at"]),
    ("ix_site_devices_created_at", "site_devices", ["created_at"]),
    ("ix_site_devices_site_panel_username", "site_devices", ["site_panel_username"]),
    ("ix_site_devices_status", "site_devices", ["status"]),
    ("ix_site_messages_created_at", "site_messages", ["created_at"]),
]


def upgrade() -> None:
    for name, table, columns in _INDEXES:
        op.create_index(name, table, columns)


def downgrade() -> None:
    for name, table, _ in reversed(_INDEXES):
        op.drop_index(name, table_name=table)
