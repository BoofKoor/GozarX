"""the site's Phase E copy: four FAQ questions, and two homepage claims made true

FAQ items are seeded ONCE (the ``seeded_site_faq`` marker), so a question added to ``seed_faq``
never reaches a running install; this is how the four Phase E adds do (a location that won't
connect, mobile data, what is kept about a visitor, the site being down). They go only into a table
that already has rows: on a fresh install the table is still empty here — migrations run before the
seeder — and the seeder then writes every default, these included; an install whose operator
removed every question keeps none. ``ON CONFLICT (locale, question) DO NOTHING`` leaves a question
the operator already wrote alone, and each lands after that locale's last question.

``site_copy_loc_sub`` / ``site_copy_app_sub`` rows that still hold the OLD in-code default verbatim
are blanked, as ``a42488f9321a`` did for the hero chips: the old sentences named Ukraine, Germany
and the USA whether or not the squad served them, and promised "every popular client". A row saved
with that text unchanged is not a customisation, and would keep the claim on the page over the new
defaults (the live location list, the apps the site actually links). Blank is the editor's own
"use the site's copy". Anything an operator reworded is untouched.

Revision ID: 5b7e2c9d4a61
Revises: 1d81a25d3ea5
Create Date: 2026-09-30
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision: str = "5b7e2c9d4a61"
down_revision: str | None = "1d81a25d3ea5"
branch_labels: str | None = None
depends_on: str | None = None

# (locale, category, question, answer) — verbatim from gozar/seed_faq.py, which a test checks.
FAQ_ADDED: tuple[tuple[str, str, str, str], ...] = (
    (
        "fa",
        "trouble",
        "یک لوکیشن وصل نمی‌شود؛ باید تا کانفیگ بعدی صبر کنم؟",
        "نه. تا وقتی کانفیگت فعال است، از صفحهٔ «کانفیگ من» می‌توانی لوکیشن دیگری انتخاب کنی. "
        "لینک تازهٔ همان لوکیشن را در اپت وارد کن؛ حجم و زمان کانفیگ همان قبلی است.",
    ),
    (
        "fa",
        "trouble",
        "روی اینترنت همراه هم کار می‌کند؟",
        "بله؛ کانفیگ به نوع اینترنت بستگی ندارد و روی وای‌فای و اینترنت همراه هر دو قابل استفاده "
        "است. اختلال‌ها ولی بین اپراتورها فرق دارد؛ اگر روی یکی وصل نشد، لوکیشن دیگری را امتحان "
        "کن.",
    ),
    (
        "fa",
        "start",
        "چه اطلاعاتی از من نگه داشته می‌شود؟",
        "برای دریافت کانفیگ نام، ایمیل یا شماره نمی‌گیریم. این مرورگر با یک کوکی امضاشده شناخته "
        "می‌شود؛ یک اثر انگشت سبک مرورگر و هشی از محدودهٔ شبکه‌ات (نه خود IP) هم فقط برای "
        "جلوگیری از سوءاستفاده نگه داشته می‌شود، و حجم مصرفی کانفیگت برای سقف روزانه شمرده "
        "می‌شود. جزئیات در صفحهٔ حریم خصوصی است.",
    ),
    (
        "fa",
        "trouble",
        "اگر سایت باز نشد، کانفیگم هم قطع می‌شود؟",
        "نه. کانفیگی که در اپت وارد کرده‌ای به این سایت وابسته نیست و تا پایان زمانش کار می‌کند. "
        "اگر قبلاً در همین مرورگر کانفیگ گرفته‌ای، آخرین لینکش برای صفحهٔ آفلاین سایت هم نگه "
        "داشته می‌شود.",
    ),
    (
        "en",
        "trouble",
        "A location won't connect — do I have to wait for my next config?",
        "No. While your config is active you can pick another location on the “My config” page. "
        "Import that location's new link into your app — your volume and time stay the same.",
    ),
    (
        "en",
        "trouble",
        "Does it work on mobile data?",
        "Yes — the config doesn't depend on the kind of connection, so it works on Wi-Fi and "
        "mobile data alike. Disruptions differ between carriers, though: if it won't connect on "
        "one, try another location.",
    ),
    (
        "en",
        "start",
        "What do you keep about me?",
        "We take no name, email or phone number to claim a config. This browser is recognised by "
        "a signed cookie; a light browser fingerprint and a hash of your network range (not the "
        "IP itself) are kept only to prevent abuse, and your config's usage is counted for the "
        "daily cap. The details are on the Privacy page.",
    ),
    (
        "en",
        "trouble",
        "If the site won't open, does my config stop working?",
        "No. A config you've imported into your app doesn't depend on this site and keeps "
        "working until its time is up. If you've claimed one in this browser before, its last "
        "link is kept for the site's offline page too.",
    ),
)

# (content key, language, OLD in-code default the row may have been saved with)
_COPY: tuple[tuple[str, str, str], ...] = (
    ("site_copy_loc_sub", "fa", "کانفیگ اوکراین، آلمان، آمریکا و بیشتر — همه رایگان و روزانه."),
    ("site_copy_loc_sub", "en", "Ukraine, Germany, USA and more — all free, every day."),
    (
        "site_copy_app_sub",
        "fa",
        "کانفیگ با همهٔ کلاینت‌های محبوب کار می‌کند. راهنمای اپ دستگاهت را باز کن.",
    ),
    (
        "site_copy_app_sub",
        "en",
        "Configs work with every popular client. Open the guide for your device's app.",
    ),
)

# Every parameter is CAST: `:locale` is used twice, and asyncpg refuses to deduce one type for a
# bare parameter in a SELECT list and in a comparison.
_INSERT = sa.text(
    "INSERT INTO site_faq_items (locale, category, question, answer, position, published)"
    " SELECT CAST(:locale AS VARCHAR), CAST(:category AS VARCHAR), CAST(:question AS VARCHAR),"
    " CAST(:answer AS TEXT),"
    " (SELECT COALESCE(MAX(position), -1) + 1 FROM site_faq_items"
    " WHERE locale = CAST(:locale AS VARCHAR)), true"
    " WHERE EXISTS (SELECT 1 FROM site_faq_items)"
    " ON CONFLICT ON CONSTRAINT uq_site_faq_locale_question DO NOTHING"
)
_DELETE = sa.text(
    "DELETE FROM site_faq_items"
    " WHERE locale = :locale AND question = :question AND answer = :answer"
)
# ``language`` is a Postgres enum — cast it to text so the bound string param compares cleanly.
_BLANK = sa.text(
    "UPDATE content SET body = '' WHERE key = :key AND language::text = :lang AND body = :old"
)


def upgrade() -> None:
    conn = op.get_bind()
    for locale, category, question, answer in FAQ_ADDED:
        conn.execute(
            _INSERT,
            {"locale": locale, "category": category, "question": question, "answer": answer},
        )
    for key, lang, old in _COPY:
        conn.execute(_BLANK, {"key": key, "lang": lang, "old": old})


def downgrade() -> None:
    # The added questions go while they still hold this migration's text; an operator's edit to one
    # makes it theirs and it stays. The blanked copy rows stay blank: blank renders the in-code
    # copy, which after a code downgrade is the old sentence again.
    conn = op.get_bind()
    for locale, _category, question, answer in FAQ_ADDED:
        conn.execute(_DELETE, {"locale": locale, "question": question, "answer": answer})
