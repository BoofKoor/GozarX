"""``content`` table — editable user-facing bot copy, keyed by (key, language)."""

from __future__ import annotations

from sqlalchemy import Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from gozar.db.base import Base
from gozar.db.models.enums import Language, language_enum


class Content(Base):
    __tablename__ = "content"
    __table_args__ = (UniqueConstraint("key", "language", name="uq_content_key_language"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    key: Mapped[str] = mapped_column(String(128))
    language: Mapped[Language] = mapped_column(language_enum)
    body: Mapped[str] = mapped_column(Text)
