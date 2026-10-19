"""the Telegram console's copy: two templates retired, the home's prose reworded

Phase 29 rebuilt ``/admin`` on rich messages. Two of its texts were whole templated screens — the
stats list and the user card, a bullet per figure with a ``{token}`` in each — and those screens are
tables now, their labels the console's own chrome (``ui/console_text``). Nothing reads
``admin_stats`` / ``admin_user_card`` any more, so their rows are removed: left in place they would
sit in the panel's Texts editor as copy that changes nothing, edited or not.

``admin_menu`` stays — it is the line above the home's buttons — but the home now draws its own
title, so the default loses the «🛠 پنل مدیریت» it used to open with. Only rows still holding the OLD
default verbatim are reworded; anything an operator wrote is left as they wrote it. Idempotent: on
a fresh database the WHERE clauses match nothing (the seeder then inserts the new default).

Revision ID: 7c3e9a1d5f20
Revises: 5b7e2c9d4a61
Create Date: 2026-10-19
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision: str = "7c3e9a1d5f20"
down_revision: str | None = "5b7e2c9d4a61"
branch_labels: str | None = None
depends_on: str | None = None

_RETIRED = ("admin_stats", "admin_user_card")

# (language, OLD default, NEW default)
_MENU: tuple[tuple[str, str, str], ...] = (
    ("fa", "🛠 پنل مدیریت\nیک گزینه را انتخاب کنید:", "یک بخش را از دکمه‌های زیر انتخاب کنید."),
    ("en", "🛠 Admin panel\nChoose an option:", "Pick a section below."),
    ("ru", "🛠 Панель администратора\nВыберите действие:", "Выберите раздел ниже."),
)

# ``language`` is a Postgres enum — cast it to text so the bound string param compares cleanly.
_MENU_STMT = sa.text(
    "UPDATE content SET body = :new"
    " WHERE key = 'admin_menu' AND language::text = :lang AND body = :old"
)


def upgrade() -> None:
    conn = op.get_bind()
    conn.execute(sa.text("DELETE FROM content WHERE key IN :keys").bindparams(
        sa.bindparam("keys", expanding=True)
    ), {"keys": list(_RETIRED)})
    for lang, old, new in _MENU:
        conn.execute(_MENU_STMT, {"lang": lang, "old": old, "new": new})


def downgrade() -> None:
    # The reworded menu line goes back; the retired templates come back from the old seeder's
    # add_default on its next boot (an older build reads them again).
    conn = op.get_bind()
    for lang, old, new in _MENU:
        conn.execute(_MENU_STMT, {"lang": lang, "old": new, "new": old})
