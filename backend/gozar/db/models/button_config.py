"""``button_configs`` table — admin overrides over the in-code button catalogue (Phase 7c).

One row per overridden button ``key``; absence = use the code/catalogue default. ``labels`` is a
partial ``{lang: text}`` override (missing langs fall back to the i18n default); ``row_index`` /
``position`` reorder it (null = keep the structural default); ``is_visible=False`` hides a
non-critical button. Read through ``services.button_service.ButtonService`` (Redis-cached).
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, DateTime, Integer, String, func, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from gozar.db.base import Base


class ButtonConfig(Base):
    __tablename__ = "button_configs"

    key: Mapped[str] = mapped_column(String(64), primary_key=True)
    labels: Mapped[dict[str, str] | None] = mapped_column(JSONB, nullable=True)
    is_visible: Mapped[bool] = mapped_column(Boolean, server_default=text("true"), nullable=False)
    row_index: Mapped[int | None] = mapped_column(Integer, nullable=True)
    position: Mapped[int | None] = mapped_column(Integer, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
