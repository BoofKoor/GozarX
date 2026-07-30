"""refresh unedited site-copy defaults to the live SEO values

The site's hero title/subtitle + homepage meta title/description are editable ``site_*`` content rows,
but the site never actually read them (it rendered its in-code copy) — so the seeded values drifted
from what the site shows. Now that the site reads these rows (GET /api/public/site-copy), an unedited
seed row would REPLACE the good live copy. This migration refreshes each of those four keys (fa+en) to
the current live value — but ONLY where the stored body still equals the OLD seed default, so any admin
edit (e.g. the hero subtitle the owner already customized) is preserved untouched.

Idempotent: on a fresh DB the rows already hold the new value, so the WHERE clause matches nothing.

Revision ID: 4a1e7c9d2f80
Revises: d3f7a1c9b2e4
Create Date: 2026-07-30 00:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "4a1e7c9d2f80"
down_revision: str | None = "d3f7a1c9b2e4"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# (key, language, OLD seed default, NEW live default). Only rows whose body still == OLD are updated,
# so a customized row (body != OLD) is never overwritten.
_REFRESH: tuple[tuple[str, str, str, str], ...] = (
    (
        "site_meta_title",
        "fa",
        "گذرایکس — کانفیگ آزمایشی رایگان روزانه",
        "کانفیگ رایگان V2Ray روزانه، بدون ثبت‌نام | گذرایکس GozarX",
    ),
    (
        "site_meta_title",
        "en",
        "GozarX — Free daily trial config",
        "GozarX — Free daily V2Ray config, no signup",
    ),
    (
        "site_meta_description",
        "fa",
        "هر روز یک کانفیگ آزمایشی رایگان بگیر — بدون ثبت‌نام، سریع و ساده. حجم روزانه‌ات را با دعوت دوستان بیشتر کن.",
        "هر روز یک کانفیگ رایگان و اختصاصی V2Ray/VLESS بگیر — بدون ثبت‌نام و شماره. لوکیشن دلخواه را انتخاب کن و حجم روزانه‌ات را با دعوت دوستان بیشتر کن.",
    ),
    (
        "site_meta_description",
        "en",
        "Get a free daily trial config — no signup, fast and simple. Grow your daily volume by inviting friends.",
        "Get a fresh personal V2Ray/VLESS config every day — no signup, no phone. Pick your location and grow your daily volume by inviting friends.",
    ),
    (
        "site_hero_title",
        "fa",
        "کانفیگ آزمایشی رایگان، هر روز",
        "کانفیگ رایگان و پرسرعت، در چند ثانیه",
    ),
    ("site_hero_title", "en", "A free trial config, every day", "Free, fast configs — in seconds"),
    (
        "site_hero_sub",
        "fa",
        "بدون ثبت‌نام و بدون ایمیل. کانفیگ امروزت را بگیر و با دعوت دوستان حجم روزانه‌ات را بیشتر کن.",
        "هر روز یک کانفیگ آزمایشی رایگان بگیر؛ لوکیشن دلخواهت را انتخاب کن و بدون ثبت‌نام وصل شو. با دعوت دوستان هم حجم روزانه‌ات بیشتر می‌شود.",
    ),
    (
        "site_hero_sub",
        "en",
        "No signup, no email. Grab today's config and grow your daily volume by inviting friends.",
        "Grab a free trial config every day; pick your location and connect with no signup. Invite friends and your daily volume grows too.",
    ),
)

# ``language`` is a Postgres enum — cast it to text so the bound string param compares cleanly.
_STMT = sa.text(
    "UPDATE content SET body = :new WHERE key = :key AND language::text = :lang AND body = :old"
)


def upgrade() -> None:
    conn = op.get_bind()
    for key, lang, old, new in _REFRESH:
        conn.execute(_STMT, {"key": key, "lang": lang, "old": old, "new": new})


def downgrade() -> None:
    # Reverse only rows that still hold the value this migration set (i.e. not edited since).
    conn = op.get_bind()
    for key, lang, old, new in _REFRESH:
        conn.execute(_STMT, {"key": key, "lang": lang, "old": new, "new": old})
