"""``site_messages`` table — the website contact-form inbox.

Matches the phase-5 contact form: a subject, a message body, and an OPTIONAL reply handle (email or
any way to reach back — never a Telegram handle). Read in the admin 'website' section.
``device_uuid`` is a plain correlation column (nullable, no FK); it outlives device resets.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import BigInteger, Boolean, DateTime, String, Text, func, text
from sqlalchemy.orm import Mapped, mapped_column

from gozar.db.base import Base


class SiteMessage(Base):
    __tablename__ = "site_messages"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    subject: Mapped[str] = mapped_column(String(200))
    body: Mapped[str] = mapped_column(Text)
    # Optional way for support to reply (e.g. an email). Blank when the user left none.
    reply_handle: Mapped[str | None] = mapped_column(String(200), nullable=True)
    locale: Mapped[str] = mapped_column(String(8), default="fa", server_default="fa")
    # Correlate to the sending device when known (plain column, not a FK — survives deletion).
    device_uuid: Mapped[str | None] = mapped_column(String(36), nullable=True)
    read: Mapped[bool] = mapped_column(Boolean, default=False, server_default=text("false"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
