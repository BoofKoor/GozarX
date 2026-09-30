"""The panel reading cache and the squad-online recorder (no database for the pure parts).

What these pin down is the performance contract behind the dashboard: a request never pages the
panel, a reading is shared rather than re-fetched per poll, a failure is remembered briefly instead
of re-paid on every poll, and the squad sweep runs in the worker, once at a time.
"""

from __future__ import annotations

import asyncio
import json
import time

import fakeredis.aioredis

from gozar.remnawave.schemas import SystemStats
from gozar.services.panel_cache import (
    SQUAD_ONLINE_JOB,
    SQUAD_ONLINE_KEY,
    SYSTEM_STATS_KEY,
    read_squad_online,
    read_system_stats,
    refresh_system_stats,
    request_squad_online_refresh,
    write_squad_online,
)


class _CountingPanel:
    def __init__(self, up: bool = True, delay: float = 0.0) -> None:
        self.calls = 0
        self.up = up
        self.delay = delay

    async def system_stats(self) -> SystemStats | None:
        self.calls += 1
        if self.delay:
            await asyncio.sleep(self.delay)
        return SystemStats(online_now=7, total_users=3) if self.up else None


def _redis() -> fakeredis.aioredis.FakeRedis:
    return fakeredis.aioredis.FakeRedis(decode_responses=True)


async def test_a_reading_is_shared_instead_of_refetched_per_poll() -> None:
    redis, panel = _redis(), _CountingPanel()
    first = await read_system_stats(panel, redis)
    second = await read_system_stats(panel, redis)
    assert first.stats is not None and first.stats.online_now == 7
    assert second.stats is not None and second.stats.online_now == 7
    assert panel.calls == 1


async def test_a_stale_reading_is_refreshed() -> None:
    redis, panel = _redis(), _CountingPanel()
    await read_system_stats(panel, redis)
    await read_system_stats(panel, redis, max_age=0)
    assert panel.calls == 2


async def test_a_failed_call_is_remembered_so_polls_do_not_repay_it() -> None:
    redis, panel = _redis(), _CountingPanel(up=False)
    assert (await read_system_stats(panel, redis)).stats is None
    assert (await read_system_stats(panel, redis, max_age=0)).stats is None
    assert panel.calls == 1
    assert 0 < await redis.ttl(SYSTEM_STATS_KEY) <= 20


async def test_a_refresh_always_asks_and_records_latency() -> None:
    redis, panel = _redis(), _CountingPanel()
    await refresh_system_stats(panel, redis)
    reading = await refresh_system_stats(panel, redis)
    assert panel.calls == 2 and reading.latency_ms is not None


async def test_a_hanging_panel_is_cut_off(monkeypatch) -> None:
    monkeypatch.setattr("gozar.services.panel_cache.SYSTEM_STATS_TIMEOUT", 0.05)
    redis, panel = _redis(), _CountingPanel(delay=5)
    started = time.monotonic()
    reading = await refresh_system_stats(panel, redis)
    assert reading.stats is None and time.monotonic() - started < 2


async def test_an_unreadable_cache_entry_is_a_miss() -> None:
    redis, panel = _redis(), _CountingPanel()
    await redis.set(SYSTEM_STATS_KEY, "not json")
    assert (await read_system_stats(panel, redis)).stats is not None
    assert panel.calls == 1


async def test_squad_online_round_trip_and_age() -> None:
    redis = _redis()
    assert await read_squad_online(redis) is None
    await write_squad_online(redis, 42)
    count, age = await read_squad_online(redis)  # type: ignore[misc]
    assert count == 42 and 0 <= age < 5
    # An entry from before this key's format (a bare int) is ignored rather than misread.
    await redis.set(SQUAD_ONLINE_KEY, "17")
    assert await read_squad_online(redis) is None


class _Arq:
    def __init__(self) -> None:
        self.jobs: list[tuple[str, str | None]] = []

    async def enqueue_job(self, name: str, *args: object, _job_id: str | None = None) -> None:
        self.jobs.append((name, _job_id))


async def test_a_refresh_request_is_deduplicated_by_job_id() -> None:
    arq = _Arq()
    await request_squad_online_refresh(arq)
    await request_squad_online_refresh(None)  # no queue (dev without a bot token): a no-op
    assert arq.jobs == [(SQUAD_ONLINE_JOB, SQUAD_ONLINE_JOB)]


async def test_worker_sweep_records_the_count_once_at_a_time(db_sessions) -> None:
    from gozar.db.repositories.settings import SettingsRepository
    from gozar.worker.tasks import refresh_squad_online

    async with db_sessions() as session:
        await SettingsRepository(session).set("trial_internal_squad", "sq-1")
        await session.commit()

    class _Panel:
        def __init__(self) -> None:
            self.sweeps = 0

        async def squad_online_count(self, squads: set[str]) -> int:
            self.sweeps += 1
            assert squads == {"sq-1"}
            await asyncio.sleep(0.05)
            return 5

    redis, panel = _redis(), _Panel()
    ctx = {"cache_redis": redis, "panel": panel, "sessionmaker": db_sessions}
    await asyncio.gather(refresh_squad_online(ctx), refresh_squad_online(ctx))
    assert panel.sweeps == 1
    recorded = json.loads(await redis.get(SQUAD_ONLINE_KEY))
    assert recorded["count"] == 5
