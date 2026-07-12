"""``site_devices`` table — the website's device-based identity (no login, no Telegram).

The site's analogue of the bot ``users`` row, but keyed by an opaque device ``uuid`` (signed into
an httpOnly cookie) instead of a Telegram id. Site users live ENTIRELY in these ``site_*`` tables
and never touch the bot ``users`` table. ``last_claim_at`` is the rolling-cooldown anchor (set at
provision time, so it lines up with the panel account's own expiry), mirroring
``users.last_claim_at``.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Integer, String, func, text
from sqlalchemy.orm import Mapped, mapped_column

from gozar.db.base import Base


class SiteDeviceStatus:
    """Device lifecycle states (plain strings — no native enum, to avoid enum coupling)."""

    available = "available"
    active_config = "active_config"
    blocked = "blocked"


class SiteDevice(Base):
    __tablename__ = "site_devices"

    # Opaque device id signed into the httpOnly cookie (UUID4 text). The whole identity.
    uuid: Mapped[str] = mapped_column(String(36), primary_key=True)
    # Short human-readable public handle (``GZ-7K3F9A``) — the account id shown to the user and used
    # as the referral code in invite links. Unique; minted at first sight, backfilled for old rows.
    handle: Mapped[str | None] = mapped_column(String(16), unique=True, index=True, nullable=True)
    status: Mapped[str] = mapped_column(
        String(16), default=SiteDeviceStatus.available, server_default=SiteDeviceStatus.available
    )
    # Remnawave username of the current site trial account (s-prefixed); None when not holding one.
    site_panel_username: Mapped[str | None] = mapped_column(String(64), nullable=True)
    # Provision time of the last trial — the rolling-cooldown anchor (aligned with panel expiry).
    last_claim_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    referral_count: Mapped[int] = mapped_column(Integer, default=0, server_default=text("0"))
    # Inviter's device uuid. Plain column (not a FK): the inviter row is guaranteed but we keep it
    # decoupled like the bot's ``users.referred_by``.
    referred_by: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    # Daily-streak bookkeeping (site_reward_streak_mb after site_streak_days consecutive days).
    streak_count: Mapped[int] = mapped_column(Integer, default=0, server_default=text("0"))
    last_streak_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    # Light anti-abuse signals captured at first sight (never a hard block on their own).
    fingerprint_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    ip_bucket: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
