"""P9a — admin-side site repository methods: landing CRUD, inbox read/mark-read, funnel aggregates.

DB-gated (needs TEST_DATABASE_URL / Postgres); skipped in the default run like the other repo tests.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy.exc import IntegrityError

from gozar.db.repositories.push_subscription import PushSubscriptionRepository
from gozar.db.repositories.site_claim import SiteClaimRepository
from gozar.db.repositories.site_device import SiteDeviceRepository
from gozar.db.repositories.site_landing_page import SiteLandingPageRepository
from gozar.db.repositories.site_message import SiteMessageRepository


async def test_landing_crud_and_unique(session):
    repo = SiteLandingPageRepository(session)
    page = await repo.create(slug="free-v2ray", locale="fa", title="کانفیگ رایگان")
    assert page.id is not None
    assert page.published is True

    assert (await repo.get(page.id)).title == "کانفیگ رایگان"
    assert (await repo.get_by_slug("free-v2ray", "fa")).id == page.id
    assert await repo.get_by_slug("free-v2ray", "en") is None

    # the same slug in the other locale is allowed (uniqueness is on the pair)
    await repo.create(slug="free-v2ray", locale="en", title="Free config")
    assert len(await repo.list()) == 2
    assert len(await repo.list(locale="fa")) == 1

    # a duplicate (slug, locale) violates the unique constraint
    with pytest.raises(IntegrityError):
        await repo.create(slug="free-v2ray", locale="fa", title="dup")


async def test_landing_update_published_and_delete(session):
    repo = SiteLandingPageRepository(session)
    page = await repo.create(slug="s", locale="fa", title="t", published=False)
    await repo.update(
        page,
        slug="s",
        locale="fa",
        title="t2",
        meta_description="m",
        heading="h",
        body="b",
        location_remark=None,
        published=True,
    )
    fetched = await repo.get(page.id)
    assert fetched.title == "t2" and fetched.published is True

    # list_published returns only published rows
    await repo.create(slug="hidden", locale="fa", title="x", published=False)
    assert [p.slug for p in await repo.list_published()] == ["s"]

    await repo.delete(fetched)
    assert await repo.get(page.id) is None


async def test_landing_add_default_is_idempotent(session):
    repo = SiteLandingPageRepository(session)
    await repo.add_default(slug="seeded", locale="fa", title="v1", body="<p>b</p>")
    page = await repo.get_by_slug("seeded", "fa")
    assert page is not None and page.title == "v1"

    # a second seed run with different content must NOT clobber the existing row
    await repo.add_default(slug="seeded", locale="fa", title="v2", body="<p>changed</p>")
    page = await repo.get_by_slug("seeded", "fa")
    assert page.title == "v1"
    assert len(await repo.list()) == 1


async def test_inbox_list_count_and_mark_read(session):
    repo = SiteMessageRepository(session)
    for i in range(3):
        await repo.add(
            subject=f"s{i}", body=f"b{i}", reply_handle=None, locale="fa", device_uuid=None
        )

    assert await repo.count() == 3
    assert await repo.count(unread_only=True) == 3

    page = await repo.list_page(limit=2, offset=0)
    assert len(page) == 2
    assert page[0].subject == "s2"  # newest first

    first = page[0]
    assert await repo.mark_read(first.id) is True
    assert await repo.mark_read(first.id) is False  # already read -> idempotent no-op
    assert await repo.count(unread_only=True) == 2

    unread = await repo.list_page(limit=10, offset=0, unread_only=True)
    assert first.id not in [m.id for m in unread]


async def test_funnel_aggregates(session):
    devices = SiteDeviceRepository(session)
    claims = SiteClaimRepository(session)
    push = PushSubscriptionRepository(session)

    await devices.create("uuid-1")
    await devices.create("uuid-2")
    await devices.create("uuid-3")  # never claims
    assert await devices.count() == 3
    assert (await devices.count_by_status()).get("available") == 3

    since = datetime.now(UTC) - timedelta(hours=1)
    await claims.add("uuid-1", "Germany")
    await claims.add("uuid-1", "Germany")  # same device claims twice
    await claims.add("uuid-2", "France")

    assert await claims.count_since(since) == 3
    assert await claims.distinct_device_count() == 2  # only uuid-1 and uuid-2 claimed
    assert dict(await claims.location_counts(since)) == {"Germany": 2, "France": 1}
    assert sum(n for _, n in await claims.daily_counts(since)) == 3

    await push.upsert(
        device_uuid="uuid-1", endpoint="https://ex/1", p256dh="k", auth="a", locale="fa"
    )
    await push.upsert(
        device_uuid="uuid-2", endpoint="https://ex/2", p256dh="k", auth="a", locale="fa"
    )
    assert await push.count_active() == 2


async def test_change_location_excluded_from_funnel(session):
    """B1: change-location re-picks (is_change=True) inflate history but must NOT count in the
    funnel — else a heavy switcher balloons 'configs today', the daily series, and top locations."""
    devices = SiteDeviceRepository(session)
    claims = SiteClaimRepository(session)
    await devices.create("uuid-1")

    since = datetime.now(UTC) - timedelta(hours=1)
    await claims.add("uuid-1", "Germany")  # the opening provision
    await claims.add("uuid-1", "France", is_change=True)  # switched location
    await claims.add("uuid-1", "Finland", is_change=True)  # switched again

    # Funnel stats see only the one provision (consistent with the bot's config_logs).
    assert await claims.count_since(since) == 1
    assert dict(await claims.location_counts(since)) == {"Germany": 1}
    assert sum(n for _, n in await claims.daily_counts(since)) == 1
    # History / current-location keep every delivery.
    assert await claims.count_all() == 3
    assert await claims.count_for_device("uuid-1") == 3
    assert await claims.latest_location_for_device("uuid-1") == "Finland"
    assert await claims.distinct_device_count() == 1
