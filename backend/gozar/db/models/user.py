"""``users`` table."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import BigInteger, Boolean, DateTime, Integer, String, func, text, true
from sqlalchemy.orm import Mapped, mapped_column

from gozar.db.base import Base
from gozar.db.models.enums import Language, UserStatus, language_enum, user_status_enum


class User(Base):
    __tablename__ = "users"

    # Telegram-supplied id (no sequence).
    telegram_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=False)
    status: Mapped[UserStatus] = mapped_column(
        user_status_enum, default=UserStatus.available, server_default=UserStatus.available.value
    )
    language: Mapped[Language] = mapped_column(
        language_enum, default=Language.fa, server_default=Language.fa.value
    )
    referral_count: Mapped[int] = mapped_column(Integer, default=0, server_default=text("0"))
    # Remnawave username of the current trial account (None when not holding a config).
    panel_username: Mapped[str | None] = mapped_column(String(64), nullable=True)
    reminder_enabled: Mapped[bool] = mapped_column(Boolean, default=True, server_default=true())
    # Inviter's telegram_id. Plain bigint (not a FK): the inviter may not exist as a row yet.
    referred_by: Mapped[int | None] = mapped_column(BigInteger, nullable=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    # When the user last PROVISIONED a trial (the moment claim() creates the panel account) — the
    # rolling-cooldown anchor. It lines up with the trial's own expiry (both = claim + trial_hours),
    # unlike a config_logs row timestamped at the later location-pick. None until the first claim.
    last_claim_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
