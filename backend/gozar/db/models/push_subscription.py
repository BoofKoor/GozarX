"""``push_subscriptions`` table — Web Push endpoints (the site's non-Telegram delivery channel).

One row per browser push subscription (endpoint + the p256dh/auth keys the VAPID sender needs). A
subscription is pruned ONLY when the push service reports it permanently gone (HTTP 404/410) — never
on a transient error (the v1 mass-deletion lesson). FK to ``site_devices`` (CASCADE).
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from gozar.db.base import Base


class PushSubscription(Base):
    __tablename__ = "push_subscriptions"
    __table_args__ = (UniqueConstraint("endpoint", name="uq_push_subscription_endpoint"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    device_uuid: Mapped[str] = mapped_column(
        String(36), ForeignKey("site_devices.uuid", ondelete="CASCADE"), index=True
    )
    # Push service endpoint URL (FCM / Mozilla autopush / Apple). Unique so re-subscribes dedupe.
    endpoint: Mapped[str] = mapped_column(String(512))
    p256dh: Mapped[str] = mapped_column(String(255))
    auth: Mapped[str] = mapped_column(String(255))
    # The browser's UI locale, captured at subscribe time — a server-initiated push (expiry / volume
    # nudge, broadcast) has no request context, so it localizes copy from this per-sub value.
    locale: Mapped[str] = mapped_column(String(8), default="fa", server_default="fa")
    active: Mapped[bool] = mapped_column(Boolean, default=True, server_default=text("true"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
