"""``broadcast_drafts`` table — a broadcast the operator started and has not sent.

A broadcast is the one thing in the panel that is written rather than configured: a few paragraphs,
in three languages, with the buttons and the audience that go with it. Losing that to a refresh, an
expired JWT or a second machine is the failure this exists to remove.

Kept in the database rather than in the browser on purpose. The panel is a shared operator console —
one person drafts an announcement, another sends it — and a draft only in ``localStorage`` is
invisible to everyone but the tab that typed it, gone with a cleared cache, and absent from the
phone the same admin picks up an hour later.

Deliberately NOT a ``broadcast_logs`` row with a ``draft`` status: a log row records something that
happened and is never edited, while a draft is mutable until the moment it stops being a draft. One
table doing both would need every history query to remember to exclude the unsent ones.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import BigInteger, Boolean, DateTime, Index, String, Text, func, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from gozar.db.base import Base


class BroadcastDraft(Base):
    __tablename__ = "broadcast_drafts"
    # Declared here as well as in the migration so autogenerate SEES it; left out of the model, the
    # next `make migrate` would emit a drop_index for the index the draft list depends on.
    __table_args__ = (Index("ix_broadcast_drafts_updated_at", text("updated_at DESC")),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    #: What the operator will see in the list. Derived from the body on save, so a draft never has
    #: to be named before it can be kept.
    title: Mapped[str] = mapped_column(String(120), default="", server_default="")
    body: Mapped[str] = mapped_column(Text)
    #: The same shapes the send route takes, so restoring a draft is an assignment rather than a
    #: translation: comma-separated language codes ("" = everyone), the two audience refinements,
    #: and the inline keyboard as `[{"text": …, "url": …}, …]`.
    languages: Mapped[str] = mapped_column(String(32), default="", server_default="")
    only_active: Mapped[bool] = mapped_column(Boolean, default=False, server_default=text("false"))
    only_referrers: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default=text("false")
    )
    buttons: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    #: The hour of day the operator had picked, or None if the draft was not scheduled. Just the
    #: hour: an absolute instant saved on Monday is in the past by Tuesday, and "21:00" is what was
    #: actually chosen.
    send_hour: Mapped[int | None] = mapped_column(nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
