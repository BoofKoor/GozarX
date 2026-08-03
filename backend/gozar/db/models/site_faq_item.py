"""``site_faq_items`` table — the public site's FAQ, editable from the admin 'website' section.

The FAQ used to be 16 hardcoded strings in ``frontend/site/lib/content.ts``: answering a new
recurring question meant a code change and a redeploy. These rows carry the same shape the site's
list already renders (category · question · answer), plus an explicit ``position`` so the operator
controls the order and ``published`` so an answer can be pulled without deleting it.

The defaults are seeded from ``seed_faq`` on boot, so the panel opens showing exactly what the site
shows rather than an empty table that silently replaces the built-in list.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, DateTime, Integer, String, Text, UniqueConstraint, func, text
from sqlalchemy.orm import Mapped, mapped_column

from gozar.db.base import Base

# The site groups items under these tab ids (labels live in the site's own copy — the backend only
# needs the ids). An item in an unknown category would render only under "all", so writes are
# validated against this set.
FAQ_CATEGORIES: tuple[str, ...] = ("start", "vol", "apps", "trouble")


class SiteFaqItem(Base):
    __tablename__ = "site_faq_items"
    # (locale, question) is the seed's idempotency key: re-running the seeder must not duplicate a
    # default, and it also stops an operator silently creating the same question twice.
    __table_args__ = (UniqueConstraint("locale", "question", name="uq_site_faq_locale_question"),)
    # RETURNING the server-computed timestamps on write, so serialising the row after a flush never
    # triggers a lazy sync refresh (MissingGreenlet in the async session) — same as landings.
    __mapper_args__ = {"eager_defaults": True}

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    # fa/en only — the site is bilingual, so this is a plain String, not the bot's language enum.
    locale: Mapped[str] = mapped_column(String(8), index=True)
    category: Mapped[str] = mapped_column(String(32))
    question: Mapped[str] = mapped_column(String(300))
    answer: Mapped[str] = mapped_column(Text)
    # Display order within a locale (ties broken by id, so the list is never non-deterministic).
    position: Mapped[int] = mapped_column(Integer, default=0, server_default=text("0"))
    published: Mapped[bool] = mapped_column(Boolean, default=True, server_default=text("true"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
