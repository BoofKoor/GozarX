"""the Hiddify article stops promising an illustrated Hiddify walkthrough the site does not have

The seeded ``hiddify-config`` landing closed its three steps with «اگر مرحله‌به‌مرحله با تصویر
می‌خواهی، راهنمای اتصال را باز کن» — but the connection guides are written for Happ, not Hiddify,
and carry no screenshots. The sentence now says what the guides are instead (site audit, V-08).
The seed changes with it, but landings are seeded with ``add_default`` (insert-if-absent), so a
running install keeps the old paragraph unless something rewrites it.

Only a row whose body is STILL the seeded default byte for byte is touched — the md5 of that exact
body guards the ``replace`` (the body is ~2 KB of HTML; the hash says the same thing without pasting
it here). A body an operator edited, even by a comma, is left exactly as they wrote it. Idempotent:
after the first run the hash no longer matches. ``updated_at`` moves, so the sitemap's lastmod tells
crawlers the page changed. No cache flush: the site's ISR expires within five minutes of the deploy.

Revision ID: 1d81a25d3ea5
Revises: a42488f9321a
Create Date: 2026-09-30
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision: str = "1d81a25d3ea5"
down_revision: str | None = "a42488f9321a"
branch_labels: str | None = None
depends_on: str | None = None

_SLUG = "hiddify-config"
_LOCALE = "fa"

_OLD = (
    '<p>اگر مرحله‌به‌مرحله با تصویر می‌خواهی، <a href="/guides">راهنمای اتصال</a> را باز کن؛'
    " همان جریان روی ویندوز و مک هم صدق می‌کند و فقط محل دکمهٔ Import کمی فرق دارد.</p>"
)
_NEW = (
    "<p>همین سه قدم روی ویندوز و مک هم صدق می‌کند و فقط محل دکمهٔ Import کمی فرق دارد."
    " راهنماهای اتصال ما برای اپ Happ نوشته شده‌اند، نه هیدیفای؛ اگر ترجیح می‌دهی با Happ وصل شوی،"
    ' <a href="/guides">راهنمای اتصال</a> مسیرش را برای هر سیستم‌عامل قدم‌به‌قدم نشان می‌دهد.</p>'
)
# md5 of the whole body as seeded (unchanged from the row's first release to this one), and of the
# body this migration writes — the downgrade's guard.
_OLD_BODY_MD5 = "4e4297e24c0bb0a79154fa964e6d072a"
_NEW_BODY_MD5 = "7d969ffd9bb702fe91fa3a2dc7107a7d"

_STMT = sa.text(
    "UPDATE site_landing_pages SET body = replace(body, :old, :new), updated_at = now()"
    " WHERE slug = :slug AND locale = :locale AND md5(body) = :md5"
)


def upgrade() -> None:
    op.get_bind().execute(
        _STMT, {"old": _OLD, "new": _NEW, "slug": _SLUG, "locale": _LOCALE, "md5": _OLD_BODY_MD5}
    )


def downgrade() -> None:
    op.get_bind().execute(
        _STMT, {"old": _NEW, "new": _OLD, "slug": _SLUG, "locale": _LOCALE, "md5": _NEW_BODY_MD5}
    )
