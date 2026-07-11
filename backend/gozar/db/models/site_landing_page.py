"""``site_landing_pages`` table — SEO keyword landing pages, managed in the admin 'website' section.

One row per (slug, locale): the flat ``content`` table can't carry a slug + SEO meta, so landings
get their own table. ``title``/``meta_description`` drive SEO; ``body`` is the rendered content;
``location_remark`` optionally preselects a location in the embedded claim widget. fa/en only (the
site is bilingual — no ``ru``), so ``locale`` is a plain String, not the bot's language enum.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    Boolean,
    DateTime,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from gozar.db.base import Base


class SiteLandingPage(Base):
    __tablename__ = "site_landing_pages"
    __table_args__ = (UniqueConstraint("slug", "locale", name="uq_site_landing_slug_locale"),)
    # Fetch server-computed created_at/updated_at via RETURNING on write, so reading them after a
    # flush (serializing the row in the admin API) never triggers a lazy sync refresh — which would
    # MissingGreenlet in the async session, esp. on the onupdate after an edit.
    __mapper_args__ = {"eager_defaults": True}

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    slug: Mapped[str] = mapped_column(String(128), index=True)
    locale: Mapped[str] = mapped_column(String(8))
    title: Mapped[str] = mapped_column(String(200))
    meta_description: Mapped[str] = mapped_column(String(320), default="", server_default="")
    heading: Mapped[str | None] = mapped_column(String(200), nullable=True)
    body: Mapped[str] = mapped_column(Text, default="", server_default="")
    # Optional location remark NAME to preselect in the page's claim widget.
    location_remark: Mapped[str | None] = mapped_column(String(128), nullable=True)
    published: Mapped[bool] = mapped_column(Boolean, default=True, server_default=text("true"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    # onupdate keeps the edit time fresh on every admin save (SQLAlchemy-side, no DDL change).
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
