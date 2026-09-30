"""retire the frozen numbers in the site's seeded copy («۲۴ ساعت», «+۱۲٬۰۰۰ کاربر»)

The public site stated two numbers no setting or count could move: a 24-hour renewal window (it is
``site_trial_hours``) and "12,000+ users" (a constant, not a count). The site now fills the hero's
two chips from ``/config`` and ``/stats`` and hides a chip whose figure it does not have, and the FAQ
answers were reworded to carry no number at all. The code defaults change with it — but the FAQ is
seeded with ``add_default`` (insert-if-absent), so an existing install keeps the old answers forever
unless something rewrites them.

Only rows that still hold the OLD default text verbatim are touched:

* FAQ answers → the new default wording.
* ``site_copy_trust3`` / ``site_copy_trust4`` → blank. Those rows are only ever written by an operator
  saving the field; one saved with the default text unchanged is not a customisation, and it would
  keep the frozen number on the page over the new live-filled default. Blank is the editor's own
  "use the site's copy" state.

Anything an operator actually reworded is left exactly as they wrote it. Idempotent: on a fresh
database the WHERE clauses match nothing. No cache flush is needed: the content cache and the site's
ISR both expire within five minutes of the deploy.

Revision ID: a42488f9321a
Revises: a7d3e9f1c2b5
Create Date: 2026-09-30
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision: str = "a42488f9321a"
# Re-parented onto main's head (a7d3e9f1c2b5) when the admin audit's migrations landed first — this
# is a data-only UPDATE with no dependency on them, and it had not run anywhere yet.
down_revision: str | None = "a7d3e9f1c2b5"
branch_labels: str | None = None
depends_on: str | None = None

# (locale, question, OLD seeded answer, NEW seeded answer)
_FAQ: tuple[tuple[str, str, str, str], ...] = (
    (
        "fa",
        "کانفیگ رایگان چطور کار می‌کند؟",
        "هر ۲۴ ساعت یک کانفیگ رایگان می‌گیری؛ لوکیشن را انتخاب کن، دکمه را بزن و لینک را در"
        " اپت وارد کن.",
        "هر بار که زمان کانفیگت تمام شود، یک کانفیگ رایگان تازه می‌گیری؛ لوکیشن را انتخاب کن،"
        " دکمه را بزن و لینک را در اپت وارد کن.",
    ),
    (
        "fa",
        "چطور حجم روزانه‌ام را بیشتر کنم؟",
        "با دعوت دوستان، نصب وب‌اپ و روشن‌کردن اعلان‌ها — از بخش «حجم بیشتر».",
        "با دعوت دوستان، نصب وب‌اپ و روشن‌کردن اعلان‌ها؛ هر کدام حجم روزانه‌ات را بیشتر می‌کند.",
    ),
    (
        "en",
        "How does the free config work?",
        "Every 24 hours you get a free config; pick a location, press the button and import"
        " the link into your app.",
        "Each time your config's time runs out you can claim a fresh free one; pick a location,"
        " press the button and import the link into your app.",
    ),
    (
        "en",
        "How do I grow my daily volume?",
        "By inviting friends, installing the web app and enabling notifications — from the"
        " 'More volume' section.",
        "By inviting friends, installing the web app and enabling notifications — each one"
        " adds to your daily volume.",
    ),
)

# (content key, language, OLD in-code default the row may have been saved with)
_TRUST: tuple[tuple[str, str, str], ...] = (
    ("site_copy_trust3", "fa", "هر ۲۴ ساعت تازه"),
    ("site_copy_trust3", "en", "Fresh every 24h"),
    ("site_copy_trust4", "fa", "+۱۲٬۰۰۰ کاربر"),
    ("site_copy_trust4", "en", "12,000+ users"),
)

_FAQ_STMT = sa.text(
    "UPDATE site_faq_items SET answer = :new"
    " WHERE locale = :locale AND question = :question AND answer = :old"
)
# ``language`` is a Postgres enum — cast it to text so the bound string param compares cleanly.
_TRUST_STMT = sa.text(
    "UPDATE content SET body = '' WHERE key = :key AND language::text = :lang AND body = :old"
)


def upgrade() -> None:
    conn = op.get_bind()
    for locale, question, old, new in _FAQ:
        conn.execute(_FAQ_STMT, {"locale": locale, "question": question, "old": old, "new": new})
    for key, lang, old in _TRUST:
        conn.execute(_TRUST_STMT, {"key": key, "lang": lang, "old": old})


def downgrade() -> None:
    # FAQ rows that still hold this migration's wording go back to the old answer. The cleared trust
    # rows stay blank: blank renders the in-code copy, which after a code downgrade is the old text.
    conn = op.get_bind()
    for locale, question, old, new in _FAQ:
        conn.execute(_FAQ_STMT, {"locale": locale, "question": question, "old": new, "new": old})
