"""Phase B site analytics repository methods, verified against a real Postgres schema."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from gozar.db.models.push_subscription import PushSubscription
from gozar.db.models.site_claim import SiteClaim
from gozar.db.models.site_device import SiteDevice
from gozar.db.models.site_reward import SiteReward
from gozar.db.repositories.push_subscription import PushSubscriptionRepository
from gozar.db.repositories.site_device import SiteDeviceRepository
from gozar.db.repositories.site_reward import SiteRewardRepository


async def _seed(session) -> None:
    session.add_all(
        [
            SiteDevice(uuid="d1", streak_count=5, ip_bucket="ipA", fingerprint_hash="fpX"),
            SiteDevice(uuid="d2", streak_count=0, ip_bucket="ipA", fingerprint_hash="fpX"),
            SiteDevice(uuid="d3", streak_count=3, ip_bucket="ipB", fingerprint_hash="fpY"),
            SiteDevice(uuid="d4", streak_count=8, ip_bucket=None, fingerprint_hash=None),
        ]
    )
    await session.flush()
    session.add_all(
        [
            SiteClaim(device_uuid="d1", location="DE"),  # provision
            SiteClaim(device_uuid="d2", location="NL"),  # provision
            SiteClaim(device_uuid="d3", location="DE"),  # provision
            SiteClaim(device_uuid="d3", location="NL", is_change=True),  # change — not a new device
            SiteReward(device_uuid="d1", reward_type="pwa", amount_mb=200),
            SiteReward(device_uuid="d1", reward_type="push", amount_mb=200),
            SiteReward(device_uuid="d2", reward_type="pwa", amount_mb=200),
            PushSubscription(device_uuid="d1", endpoint="e1", p256dh="k", auth="a", locale="fa"),
            PushSubscription(device_uuid="d2", endpoint="e2", p256dh="k", auth="a", locale="en"),
            PushSubscription(
                device_uuid="d3", endpoint="e3", p256dh="k", auth="a", locale="fa", active=False
            ),
        ]
    )
    await session.commit()


async def test_site_active_since(session):
    await _seed(session)
    devices = SiteDeviceRepository(session)
    # three distinct devices provisioned; the change-location row must not add a phantom device
    assert await devices.active_since(datetime.now(UTC) - timedelta(days=1)) == 3


async def test_streak_distribution_and_active(session):
    await _seed(session)
    devices = SiteDeviceRepository(session)
    now = datetime.now(UTC)
    # d4 carries a stored 8 but has never provisioned, so nothing keeps that streak alive: it
    # counts as 0. d1 (5) and d3 (3) claimed just now.
    assert await devices.streak_distribution(24, now=now) == {"0": 2, "3-6": 2}
    assert await devices.active_streak_count(3, 24, now=now) == 2  # d1(5), d3(3)


async def test_a_lapsed_streak_stops_counting(session):
    """The stored counter is written on a claim and never on the ABSENCE of one, so a device that
    stopped claiming used to keep its streak — and its place among the "active" — forever."""
    now = datetime.now(UTC)
    session.add_all(
        [
            SiteDevice(uuid="live", streak_count=6),
            SiteDevice(uuid="gone", streak_count=6),
        ]
    )
    await session.flush()
    session.add_all(
        [
            # Within the grace window (two 24h trial windows): still running.
            SiteClaim(device_uuid="live", location="DE", created_at=now - timedelta(hours=30)),
            # Three days ago: the next claim would restart this streak at 1.
            SiteClaim(device_uuid="gone", location="DE", created_at=now - timedelta(days=3)),
            # A change-location is not a provision and must not revive it.
            SiteClaim(
                device_uuid="gone",
                location="NL",
                is_change=True,
                created_at=now - timedelta(hours=1),
            ),
        ]
    )
    await session.commit()
    devices = SiteDeviceRepository(session)
    assert await devices.active_streak_count(3, 24, now=now) == 1
    assert await devices.streak_distribution(24, now=now) == {"0": 1, "3-6": 1}


async def test_anti_abuse_signals(session):
    await _seed(session)
    devices = SiteDeviceRepository(session)
    assert await devices.top_ip_buckets(min_devices=2) == [("ipA", 2)]  # ipB has only one device
    assert await devices.shared_fingerprint_device_count() == 2  # d1 & d2 share fpX


async def test_reward_economy(session):
    await _seed(session)
    totals = {t: (c, mb) for t, c, mb in await SiteRewardRepository(session).totals_by_type()}
    assert totals["pwa"] == (2, 400)
    assert totals["push"] == (1, 200)


async def test_push_health(session):
    await _seed(session)
    push = PushSubscriptionRepository(session)
    assert await push.count_by_active() == (2, 1)  # e1/e2 active, e3 inactive
    assert dict(await push.locale_breakdown()) == {"fa": 1, "en": 1}  # active only


async def test_site_analytics_empty(session):
    devices = SiteDeviceRepository(session)
    assert await devices.active_since(datetime.now(UTC) - timedelta(days=7)) == 0
    assert await devices.streak_distribution(24, now=datetime.now(UTC)) == {}
    assert await devices.top_ip_buckets() == []
    assert await devices.shared_fingerprint_device_count() == 0
    assert await SiteRewardRepository(session).totals_by_type() == []
