"""``site_rewards`` table — one-time reward grants (PWA install, notifications) per device.

Repeatable bonuses (friend invites, daily streak) are NOT rows here — they are derived from
``site_devices.referral_count`` / ``streak_count`` in the quota math. This table records only the
**one-time** grants, so a plain ``unique(device_uuid, reward_type)`` cleanly prevents double-claims
(pwa/push) without a partial index. FK to ``site_devices`` (CASCADE).
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    BigInteger,
    DateTime,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from gozar.db.base import Base


class SiteRewardType:
    """One-time reward kinds recorded in ``site_rewards`` (repeatable ones live on the device)."""

    pwa = "pwa"
    push = "push"


class SiteReward(Base):
    __tablename__ = "site_rewards"
    __table_args__ = (
        UniqueConstraint("device_uuid", "reward_type", name="uq_site_reward_device_type"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    device_uuid: Mapped[str] = mapped_column(
        String(36), ForeignKey("site_devices.uuid", ondelete="CASCADE"), index=True
    )
    reward_type: Mapped[str] = mapped_column(String(32))
    amount_mb: Mapped[int] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
