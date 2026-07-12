"""System health — a live snapshot for the admin monitoring page + the worker's history sampler.

Pings what the service depends on (Postgres, Redis, the Remnawave panel, the Telegram webhook) and
reads the host's own resource pressure (load average, memory, disk) from the stdlib — no extra deps.
Every probe is bounded and failure-tolerant: a probe that errors degrades that component to "down"
instead of raising, so one flaky dependency never blanks the whole page. Reused by the live route
(`web/routes/admin/system.py`) and the per-minute worker sampler (`worker/tasks.sample_health`).
"""

from __future__ import annotations

import json
import logging
import os
import shutil
import time
from datetime import UTC, datetime

from aiogram import Bot
from pydantic import BaseModel
from redis.asyncio import Redis
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from gozar.cache.redis import HEALTH_HISTORY_KEY, HEALTH_HISTORY_MAX
from gozar.remnawave import RemnawaveClient
from gozar.remnawave.schemas import SystemStats

logger = logging.getLogger("gozar.services.health")

_RECENT_ERROR_SECONDS = 300  # a webhook error within 5 min counts against "live" health
_PENDING_BACKLOG = 50  # pending updates above this is a degraded webhook
_RESOURCE_PRESSURE_PCT = 90.0  # mem/disk at/above this is degraded


class Probe(BaseModel):
    ok: bool
    latency_ms: float | None = None
    detail: str | None = None


class HostResources(BaseModel):
    load1: float = 0.0
    load5: float = 0.0
    load15: float = 0.0
    cpu_count: int = 1
    mem_total: int = 0
    mem_used: int = 0
    mem_pct: float = 0.0
    disk_total: int = 0
    disk_used: int = 0
    disk_pct: float = 0.0


class WebhookHealth(BaseModel):
    configured: bool
    url_set: bool = False
    pending: int = 0
    recent_error: bool = False
    last_error_at: str | None = None
    last_error: str | None = None


class HealthSnapshot(BaseModel):
    status: str  # ok | degraded | down
    generated_at: str
    db: Probe
    redis: Probe
    panel: Probe
    telegram: Probe
    webhook: WebhookHealth
    host: HostResources
    panel_stats: SystemStats | None = None


def _meminfo() -> tuple[int, int]:
    """(total_bytes, available_bytes) from /proc/meminfo; (0, 0) when unavailable."""
    try:
        vals: dict[str, int] = {}
        with open("/proc/meminfo") as f:
            for line in f:
                parts = line.split()
                key = parts[0].rstrip(":") if parts else ""
                if key in ("MemTotal", "MemAvailable") and len(parts) >= 2:
                    vals[key] = int(parts[1]) * 1024  # kB -> bytes
        return vals.get("MemTotal", 0), vals.get("MemAvailable", 0)
    except (OSError, ValueError):
        return 0, 0


def read_host_resources() -> HostResources:
    """Host pressure from the stdlib: load average, memory (/proc/meminfo), root disk usage."""
    try:
        load1, load5, load15 = os.getloadavg()
    except (OSError, AttributeError):
        load1 = load5 = load15 = 0.0
    mem_total, mem_avail = _meminfo()
    mem_used = max(mem_total - mem_avail, 0)
    try:
        usage = shutil.disk_usage("/")
        disk_total, disk_used = usage.total, usage.used
    except OSError:
        disk_total = disk_used = 0
    return HostResources(
        load1=round(load1, 2),
        load5=round(load5, 2),
        load15=round(load15, 2),
        cpu_count=os.cpu_count() or 1,
        mem_total=mem_total,
        mem_used=mem_used,
        mem_pct=round(mem_used / mem_total * 100, 1) if mem_total else 0.0,
        disk_total=disk_total,
        disk_used=disk_used,
        disk_pct=round(disk_used / disk_total * 100, 1) if disk_total else 0.0,
    )


def _ms(start: float) -> float:
    return round((time.monotonic() - start) * 1000, 1)


async def _probe_db(session: AsyncSession) -> Probe:
    start = time.monotonic()
    try:
        await session.execute(text("SELECT 1"))
    except Exception as exc:  # any DB error -> down (never raise out of a health probe)
        logger.warning("health: db probe failed (%s)", type(exc).__name__)
        return Probe(ok=False, detail="unreachable")
    return Probe(ok=True, latency_ms=_ms(start))


async def _probe_redis(redis: Redis) -> Probe:
    start = time.monotonic()
    try:
        await redis.ping()
    except Exception as exc:
        logger.warning("health: redis probe failed (%s)", type(exc).__name__)
        return Probe(ok=False, detail="unreachable")
    return Probe(ok=True, latency_ms=_ms(start))


async def _probe_panel(panel: RemnawaveClient) -> tuple[Probe, SystemStats | None]:
    start = time.monotonic()
    try:
        stats = await panel.system_stats()  # already swallows RemnawaveError -> None
    except Exception:
        return Probe(ok=False, detail="unreachable"), None
    if stats is None:
        return Probe(ok=False, latency_ms=_ms(start), detail="unreachable"), None
    return Probe(ok=True, latency_ms=_ms(start)), stats


def _to_dt(value: object) -> datetime | None:
    """Normalise a Telegram timestamp to an aware datetime. aiogram already parses
    ``last_error_date`` into a ``datetime``; tolerate a raw int/float too."""
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=UTC)
    if isinstance(value, int | float):
        try:
            return datetime.fromtimestamp(value, tz=UTC)
        except (ValueError, OSError):
            return None
    return None


async def _probe_telegram(bot: Bot | None) -> tuple[Probe, WebhookHealth]:
    if bot is None:
        return Probe(ok=False, detail="bot disabled"), WebhookHealth(configured=False)
    start = time.monotonic()
    try:
        info = await bot.get_webhook_info()
        # Parsing stays INSIDE the try: aiogram returns last_error_date as a datetime, so a stray
        # type/shape must never escape and 500 the whole monitoring page — degrade gracefully.
        last_dt = _to_dt(info.last_error_date)
        recent = bool(
            last_dt and (datetime.now(UTC) - last_dt).total_seconds() < _RECENT_ERROR_SECONDS
        )
        webhook = WebhookHealth(
            configured=True,
            url_set=bool(info.url),
            pending=info.pending_update_count or 0,
            recent_error=recent,
            last_error_at=last_dt.isoformat() if last_dt else None,
            last_error=info.last_error_message,
        )
    except Exception:
        logger.warning("health: telegram webhook probe failed")
        return Probe(ok=False, detail="unreachable"), WebhookHealth(configured=True)
    return Probe(ok=True, latency_ms=_ms(start)), webhook


def _overall(
    db: Probe, redis: Probe, panel: Probe, tg: Probe, webhook: WebhookHealth, host: HostResources
) -> str:
    if not db.ok or not redis.ok:
        return "down"  # core infra: the bot can't serve users at all
    degraded = (
        not panel.ok
        or (webhook.configured and not tg.ok)
        or webhook.pending > _PENDING_BACKLOG
        or webhook.recent_error
        or host.mem_pct >= _RESOURCE_PRESSURE_PCT
        or host.disk_pct >= _RESOURCE_PRESSURE_PCT
    )
    return "degraded" if degraded else "ok"


async def build_snapshot(
    session: AsyncSession, redis: Redis, panel: RemnawaveClient, bot: Bot | None
) -> HealthSnapshot:
    """Probe every dependency + read host resources, then derive an overall ok/degraded/down."""
    db = await _probe_db(session)
    rds = await _probe_redis(redis)
    panel_probe, stats = await _probe_panel(panel)
    tg, webhook = await _probe_telegram(bot)
    host = read_host_resources()
    return HealthSnapshot(
        status=_overall(db, rds, panel_probe, tg, webhook, host),
        generated_at=datetime.now(UTC).isoformat(),
        db=db,
        redis=rds,
        panel=panel_probe,
        telegram=tg,
        webhook=webhook,
        host=host,
        panel_stats=stats,
    )


def sample_from(snap: HealthSnapshot) -> dict[str, object]:
    """The compact history row stored each minute — responsiveness + host pressure over time."""
    return {
        "ts": snap.generated_at,
        "status": snap.status,
        "api_ms": snap.telegram.latency_ms,
        "pending": snap.webhook.pending,
        "db_ms": snap.db.latency_ms,
        "redis_ms": snap.redis.latency_ms,
        "load1": snap.host.load1,
        "mem_pct": snap.host.mem_pct,
        "disk_pct": snap.host.disk_pct,
    }


class HistoryRow(BaseModel):
    """A persisted sample, validated on read (tolerant of missing keys from older samples)."""

    ts: str = ""
    status: str = "ok"
    api_ms: float | None = None
    pending: int = 0
    db_ms: float | None = None
    redis_ms: float | None = None
    load1: float = 0.0
    mem_pct: float = 0.0
    disk_pct: float = 0.0


async def uptime_pct(redis: Redis) -> float | None:
    """Rolling availability % from the per-minute health samples (~24h window): the share that
    weren't 'down' (core infra reachable). Returns None until a sample exists, so the SPA can show
    a dash rather than a fabricated figure on a just-booted service."""
    raw = await redis.lrange(HEALTH_HISTORY_KEY, 0, HEALTH_HISTORY_MAX - 1)
    total = up = 0
    for item in raw:
        try:
            row = HistoryRow.model_validate(json.loads(item))
        except (ValueError, TypeError):
            continue
        total += 1
        if row.status != "down":
            up += 1
    if total == 0:
        return None
    return round(up / total * 100, 1)
