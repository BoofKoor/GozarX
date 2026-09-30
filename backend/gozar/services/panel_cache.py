"""Cached panel readings for the admin views.

The admin console used to ask the Remnawave panel directly on every poll: ``/system/stats`` from the
health dot on every page (every 10s), again from the dashboard, and — the expensive one — a sweep of
EVERY panel user, 500 per request and one request after another, to count who in the trial squad is
online. That sweep ran inside ``/dashboard/stats``, so the whole dashboard sat on its skeleton for
as long as the panel took to page through its users (measured: 25 sequential requests, 25s, for
12k panel users), and concurrent requests each ran their own.

Two readings live here instead, both in Redis:

* ``system_stats`` — one bounded call, cached briefly and shared by the dashboard, the health probe
  and the worker samplers. A failure is cached too (for less time), so a dead panel costs one
  timeout per window rather than one per poll.
* ``squad_online`` — the squad-scoped online count, and the same squad's "seen this week" figure
  the dashboard gauges it against. It is computed ONLY by the worker
  (``refresh_squad_online``), never on a request path; a request reads whatever was last recorded
  and, when that is stale, asks for a refresh. The sweep therefore runs at most once at a time and
  only while someone is looking at the dashboard.
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
from dataclasses import dataclass

from pydantic import ValidationError
from redis.asyncio import Redis

from gozar.remnawave.schemas import SystemStats

logger = logging.getLogger("gozar.services.panel_cache")

SYSTEM_STATS_KEY = "cache:panel:system_stats"
#: How long a successful reading is kept. The worker refreshes it every minute (``sample_health``),
#: so a web read normally finds one well inside this.
SYSTEM_STATS_TTL = 120
#: A web read older than this refreshes it inline (one bounded call).
SYSTEM_STATS_FRESH = 60
#: A failed call is remembered for this long, so an unreachable panel is not asked on every poll.
SYSTEM_STATS_DOWN_TTL = 20
#: The inline call's ceiling. The shared HTTP client allows 10s; an admin page should not.
SYSTEM_STATS_TIMEOUT = 5.0

#: v3 records the week figure beside the online one; a v2 entry (online only) is simply never read,
#: rather than served with a denominator it does not have.
SQUAD_ONLINE_KEY = "cache:squad_online:v3"
#: A recorded count younger than this is served as-is; older ones are still served (a slightly old
#: figure beats a panel-wide one), but trigger a refresh.
SQUAD_ONLINE_FRESH = 60
#: Past this the figure is dropped and the dashboard falls back to the panel-wide count.
SQUAD_ONLINE_TTL = 15 * 60
SQUAD_ONLINE_JOB = "refresh_squad_online"


@dataclass(frozen=True, slots=True)
class PanelReading:
    """One ``/system/stats`` answer (``stats`` is None when the panel did not answer)."""

    stats: SystemStats | None
    latency_ms: float | None
    at: float  # epoch seconds

    @property
    def age(self) -> float:
        return max(0.0, time.time() - self.at)


def _decode(raw: str | None) -> PanelReading | None:
    if raw is None:
        return None
    try:
        data = json.loads(raw)
        stats = data.get("stats")
        return PanelReading(
            stats=SystemStats.model_validate(stats) if stats is not None else None,
            latency_ms=data.get("latency_ms"),
            at=float(data["at"]),
        )
    except (ValueError, TypeError, KeyError, ValidationError):
        return None  # an unreadable entry is simply a miss


async def refresh_system_stats(panel: object, redis: Redis) -> PanelReading:
    """Ask the panel once (bounded) and record the answer — success or failure — for everyone."""
    start = time.monotonic()
    try:
        async with asyncio.timeout(SYSTEM_STATS_TIMEOUT):
            stats = await panel.system_stats()  # type: ignore[attr-defined]
    except Exception:  # noqa: BLE001 — a timeout or any panel failure is the same answer here
        stats = None
    latency = round((time.monotonic() - start) * 1000, 1)
    reading = PanelReading(stats=stats, latency_ms=latency if stats else None, at=time.time())
    payload = {
        "stats": stats.model_dump() if stats is not None else None,
        "latency_ms": reading.latency_ms,
        "at": reading.at,
    }
    try:
        await redis.set(
            SYSTEM_STATS_KEY,
            json.dumps(payload),
            ex=SYSTEM_STATS_TTL if stats is not None else SYSTEM_STATS_DOWN_TTL,
        )
    except Exception:  # noqa: BLE001 — a cache write must never fail the reading itself
        logger.warning("panel_cache: could not store the system stats reading")
    return reading


async def read_system_stats(
    panel: object, redis: Redis, *, max_age: float = SYSTEM_STATS_FRESH
) -> PanelReading:
    """The latest panel reading no older than ``max_age``, refreshing it inline when needed.

    A recorded FAILURE is honoured for its own (short) lifetime whatever ``max_age`` says — the
    point of recording it is that the next poll does not wait out another timeout.
    """
    try:
        cached = _decode(await redis.get(SYSTEM_STATS_KEY))
    except Exception:  # noqa: BLE001
        cached = None
    if cached is not None and (cached.stats is None or cached.age <= max_age):
        return cached
    return await refresh_system_stats(panel, redis)


@dataclass(frozen=True, slots=True)
class SquadOnlineReading:
    """The last recorded trial-squad activity: online now, seen this week, and how old it is."""

    count: int
    week: int
    age: float  # seconds


async def read_squad_online(redis: Redis) -> SquadOnlineReading | None:
    """The last recorded squad-scoped online figures, else None."""
    try:
        raw = await redis.get(SQUAD_ONLINE_KEY)
        if raw is None:
            return None
        data = json.loads(raw)
        return SquadOnlineReading(
            count=int(data["count"]),
            week=int(data["week"]),
            age=max(0.0, time.time() - float(data["at"])),
        )
    except (ValueError, TypeError, KeyError):
        return None
    except Exception:  # noqa: BLE001 — Redis trouble reads as "nothing recorded"
        return None


async def write_squad_online(redis: Redis, count: int, week: int) -> None:
    payload = {"count": int(count), "week": int(week), "at": time.time()}
    await redis.set(SQUAD_ONLINE_KEY, json.dumps(payload), ex=SQUAD_ONLINE_TTL)


async def request_squad_online_refresh(arq: object | None) -> None:
    """Ask the worker to recount, without waiting for it. Deduplicated by job id, so any number of
    dashboards polling at once still produce one sweep. A missing queue (no bot token in dev) or a
    Redis hiccup just means the stale figure is served a little longer."""
    if arq is None:
        return
    try:
        await arq.enqueue_job(SQUAD_ONLINE_JOB, _job_id=SQUAD_ONLINE_JOB)  # type: ignore[attr-defined]
    except Exception:  # noqa: BLE001
        logger.warning("panel_cache: could not queue the squad online refresh")
