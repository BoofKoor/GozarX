"""Site tables — registration on Base.metadata, column defaults, FK cascade, unique constraints.

The registration test is DB-free (guards the ``models/__init__.py`` import — an unregistered model
is silently invisible to both autogenerate and create_all). The rest are DB-gated (the ``session``
fixture builds a fresh schema from ``Base.metadata`` and skips without ``TEST_DATABASE_URL``).
"""

from __future__ import annotations

import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from gozar.db import models  # noqa: F401  (register site tables on Base.metadata)
from gozar.db.base import Base
from gozar.db.models.push_subscription import PushSubscription
from gozar.db.models.site_claim import SiteClaim
from gozar.db.models.site_device import SiteDevice, SiteDeviceStatus
from gozar.db.models.site_landing_page import SiteLandingPage
from gozar.db.models.site_reward import SiteReward, SiteRewardType

_SITE_TABLES = (
    "site_devices",
    "site_claims",
    "site_rewards",
    "push_subscriptions",
    "site_messages",
    "site_landing_pages",
)


def test_all_site_tables_registered() -> None:
    registered = set(Base.metadata.tables)
    for table in _SITE_TABLES:
        assert table in registered, f"{table} not registered — will be invisible to migrations"


async def test_site_device_defaults(session) -> None:
    device = SiteDevice(uuid="dev-defaults")
    session.add(device)
    await session.flush()
    await session.refresh(device)
    assert device.status == SiteDeviceStatus.available
    assert device.referral_count == 0
    assert device.streak_count == 0
    assert device.site_panel_username is None
    assert device.last_claim_at is None
    assert device.created_at is not None


async def test_claim_cascades_on_device_delete(session) -> None:
    session.add(SiteDevice(uuid="dev-cascade"))
    await session.flush()
    session.add(SiteClaim(device_uuid="dev-cascade", location="Germany"))
    await session.flush()

    device = await session.get(SiteDevice, "dev-cascade")
    await session.delete(device)
    await session.flush()

    remaining = (
        await session.scalars(select(SiteClaim).where(SiteClaim.device_uuid == "dev-cascade"))
    ).all()
    assert remaining == []


async def test_claim_location_is_by_name(session) -> None:
    session.add(SiteDevice(uuid="dev-loc"))
    await session.flush()
    session.add(SiteClaim(device_uuid="dev-loc", location="Ukraine"))
    await session.flush()
    claim = (
        await session.scalars(select(SiteClaim).where(SiteClaim.device_uuid == "dev-loc"))
    ).one()
    assert claim.location == "Ukraine"  # the remark NAME, never an index


async def test_one_time_reward_is_unique_per_device(session) -> None:
    session.add(SiteDevice(uuid="dev-reward"))
    await session.flush()
    session.add(SiteReward(device_uuid="dev-reward", reward_type=SiteRewardType.pwa, amount_mb=200))
    await session.flush()
    session.add(SiteReward(device_uuid="dev-reward", reward_type=SiteRewardType.pwa, amount_mb=200))
    with pytest.raises(IntegrityError):
        await session.flush()


async def test_push_subscription_endpoint_unique(session) -> None:
    session.add(SiteDevice(uuid="dev-push"))
    await session.flush()
    session.add(
        PushSubscription(device_uuid="dev-push", endpoint="https://push/e1", p256dh="k", auth="a")
    )
    await session.flush()
    session.add(
        PushSubscription(device_uuid="dev-push", endpoint="https://push/e1", p256dh="k2", auth="a2")
    )
    with pytest.raises(IntegrityError):
        await session.flush()


async def test_landing_slug_locale_unique(session) -> None:
    session.add(SiteLandingPage(slug="free-germany", locale="fa", title="آلمان"))
    await session.flush()
    session.add(SiteLandingPage(slug="free-germany", locale="fa", title="duplicate"))
    with pytest.raises(IntegrityError):
        await session.flush()


async def test_landing_same_slug_different_locale_ok(session) -> None:
    session.add(SiteLandingPage(slug="free-ukraine", locale="fa", title="اوکراین"))
    session.add(SiteLandingPage(slug="free-ukraine", locale="en", title="Ukraine"))
    await session.flush()  # (slug, locale) unique — same slug across locales is allowed
    rows = (
        await session.scalars(select(SiteLandingPage).where(SiteLandingPage.slug == "free-ukraine"))
    ).all()
    assert {r.locale for r in rows} == {"fa", "en"}
