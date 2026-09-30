"""``touch_seen`` records one ``site_device_days`` row per device per LOCAL day.

The row is what lets a past window be counted at all (``last_seen_at`` is overwritten on each
visit), so these pin the two ways it could go missing: the hourly throttle swallowing the first
request of a new day, and a freshly minted device whose ``last_seen_at`` came from the server
default and so looked "just seen".
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from sqlalchemy import select

from gozar.config.reporting import DISPLAY_TZ
from gozar.db.models.site_device_day import SiteDeviceDay
from gozar.db.repositories import site_device as site_device_module
from gozar.db.repositories.site_device import SiteDeviceRepository


class _Clock(datetime):
    current: datetime = datetime(2026, 9, 30, tzinfo=UTC)

    @classmethod
    def now(cls, tz=None):  # type: ignore[override]
        return cls.current if tz is None else cls.current.astimezone(tz)


def _local(y: int, m: int, d: int, hh: int, mm: int) -> datetime:
    return datetime(y, m, d, hh, mm, tzinfo=DISPLAY_TZ).astimezone(UTC)


async def _days(session) -> list[tuple[str, datetime]]:
    rows = (await session.scalars(select(SiteDeviceDay).order_by(SiteDeviceDay.day))).all()
    return [(r.day.isoformat(), r.first_at) for r in rows]


async def test_a_new_local_day_writes_even_inside_the_throttle(session, monkeypatch) -> None:
    monkeypatch.setattr(site_device_module, "datetime", _Clock)
    repo = SiteDeviceRepository(session)
    device = await repo.create("dev-1")
    # Seen at 23:50 local; the next request is 20 minutes later, but on the NEXT local day.
    device.last_seen_at = _local(2026, 9, 29, 23, 50)
    _Clock.current = _local(2026, 9, 30, 0, 10)
    await repo.touch_seen(device)

    _Clock.current = _local(2026, 9, 30, 0, 20)  # same day, inside the hour: throttled
    await repo.touch_seen(device)
    await session.flush()

    assert await _days(session) == [("2026-09-30", _local(2026, 9, 30, 0, 10))]
    assert device.last_seen_at == _local(2026, 9, 30, 0, 10)


async def test_the_visit_that_minted_a_device_is_recorded(session) -> None:
    repo = SiteDeviceRepository(session)
    device, created = await repo.get_or_create("dev-2")
    assert created and device.last_seen_at is not None  # the server default looks "just seen"
    await repo.touch_seen(device, minted=created)
    await session.flush()
    assert len(await _days(session)) == 1


async def test_two_requests_on_one_day_keep_one_row(session, monkeypatch) -> None:
    monkeypatch.setattr(site_device_module, "datetime", _Clock)
    repo = SiteDeviceRepository(session)
    device = await repo.create("dev-3")
    device.last_seen_at = _local(2026, 9, 30, 8, 0)
    _Clock.current = _local(2026, 9, 30, 10, 0)  # past the throttle, same day
    await repo.touch_seen(device)
    _Clock.current = _local(2026, 9, 30, 12, 0)
    await repo.touch_seen(device)
    await session.flush()

    # first_at stays the FIRST request of the day: a window ending mid-day depends on it.
    assert await _days(session) == [("2026-09-30", _local(2026, 9, 30, 10, 0))]
    assert device.last_seen_at == _local(2026, 9, 30, 12, 0)
    assert _Clock.current - device.last_seen_at < timedelta(seconds=1)
