"""System health: the overall-status logic + host probe (no DB), and the DB-gated snapshot/sampler.

The pure ``_overall`` rules and ``read_host_resources`` need no database. ``build_snapshot`` and the
worker ``sample_health`` use the real ``session`` / ``db_sessions`` fixtures (skipped without
``TEST_DATABASE_URL``) with fakeredis and a stub panel.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import fakeredis.aioredis

from gozar.cache.redis import HEALTH_HISTORY_KEY
from gozar.remnawave.schemas import SystemStats
from gozar.seed import DEFAULT_CONTENT
from gozar.services.health import (
    HostResources,
    Probe,
    WebhookHealth,
    _overall,
    _to_dt,
    build_snapshot,
    read_host_resources,
    sample_from,
)

_OK = Probe(ok=True)
_DOWN = Probe(ok=False)


class _PanelDown:
    async def system_stats(self) -> None:
        return None


class _PanelUp:
    async def system_stats(self) -> SystemStats:
        return SystemStats(
            online_now=1, cpu_cores=4, mem_total=100, mem_used=50, uptime_seconds=3600
        )


class _Bot:
    """Minimal stand-in for the aiogram Bot. ``last_error_date`` is a ``datetime`` — exactly how
    aiogram parses it (the live bug: the old code assumed a Unix int and 500'd the page)."""

    def __init__(self, last_error_date: object = None, message: str | None = None) -> None:
        self._led = last_error_date
        self._msg = message

    async def get_webhook_info(self) -> SimpleNamespace:
        return SimpleNamespace(
            url="https://x/tg/secret",
            pending_update_count=3,
            last_error_date=self._led,
            last_error_message=self._msg,
        )


def test_config_created_toast_seeded_all_langs() -> None:
    toast = DEFAULT_CONTENT.get("config_created_toast", {})
    assert {lang.value for lang in toast} == {"fa", "en", "ru"} and all(toast.values())


def test_read_host_resources_returns_sane_values() -> None:
    host = read_host_resources()
    assert host.cpu_count >= 1
    assert host.mem_total > 0 and 0.0 <= host.mem_pct <= 100.0
    assert 0.0 <= host.disk_pct <= 100.0


def test_overall_down_on_core_infra() -> None:
    wh, host = WebhookHealth(configured=False), HostResources()
    assert _overall(_DOWN, _OK, _OK, _OK, wh, host) == "down"  # DB down
    assert _overall(_OK, _DOWN, _OK, _OK, wh, host) == "down"  # Redis down


def test_overall_degraded_on_panel_backlog_or_recent_error() -> None:
    host = HostResources()
    assert _overall(_OK, _OK, _DOWN, _OK, WebhookHealth(configured=False), host) == "degraded"
    assert (
        _overall(_OK, _OK, _OK, _OK, WebhookHealth(configured=True, pending=100), host)
        == "degraded"
    )
    assert (
        _overall(_OK, _OK, _OK, _OK, WebhookHealth(configured=True, recent_error=True), host)
        == "degraded"
    )


def test_overall_ok_when_all_healthy() -> None:
    wh = WebhookHealth(configured=True, pending=0)
    host = HostResources(mem_pct=10.0, disk_pct=10.0)
    assert _overall(_OK, _OK, _OK, _OK, wh, host) == "ok"


async def test_build_snapshot_degraded_when_panel_down(session) -> None:
    redis = fakeredis.aioredis.FakeRedis(decode_responses=True)
    snap = await build_snapshot(session, redis, _PanelDown(), None)
    assert snap.db.ok and snap.redis.ok  # real test DB + fakeredis
    assert not snap.panel.ok  # stub returns None
    assert snap.telegram.ok is False and snap.webhook.configured is False  # bot disabled
    assert snap.status == "degraded"  # core infra ok, but the panel is down
    assert snap.host.cpu_count >= 1


async def test_build_snapshot_ok_and_surfaces_panel_host(session) -> None:
    redis = fakeredis.aioredis.FakeRedis(decode_responses=True)
    snap = await build_snapshot(session, redis, _PanelUp(), None)
    assert snap.panel.ok and snap.panel_stats is not None and snap.panel_stats.cpu_cores == 4
    assert snap.status == "ok"
    sample = sample_from(snap)
    assert set(sample) >= {"ts", "status", "api_ms", "pending", "load1", "mem_pct", "disk_pct"}


async def test_sample_health_writes_capped_history(db_sessions) -> None:
    from gozar.worker.tasks import sample_health

    redis = fakeredis.aioredis.FakeRedis(decode_responses=True)
    ctx = {"sessionmaker": db_sessions, "cache_redis": redis, "panel": _PanelDown(), "bot": None}
    await sample_health(ctx)
    items = await redis.lrange(HEALTH_HISTORY_KEY, 0, -1)
    assert len(items) == 1
    row = json.loads(items[0])
    assert "ts" in row and "status" in row and "load1" in row


def test_to_dt_accepts_datetime_int_and_none() -> None:
    aware = datetime(2026, 1, 1, tzinfo=UTC)
    assert _to_dt(aware) == aware
    assert _to_dt(datetime(2026, 1, 1)).tzinfo is UTC  # naive -> assumed UTC
    assert _to_dt(1735689600) is not None  # raw int timestamp tolerated
    assert _to_dt(None) is None and _to_dt("oops") is None


async def test_build_snapshot_handles_datetime_last_error(session) -> None:
    # Regression: aiogram gives last_error_date as a datetime. A RECENT webhook error must be picked
    # up (and degrade the status) — never raise out of the probe and 500 the page.
    redis = fakeredis.aioredis.FakeRedis(decode_responses=True)
    recent = datetime.now(UTC) - timedelta(minutes=1)
    bot = _Bot(recent, "Wrong response from the webhook: 502 Bad Gateway")
    snap = await build_snapshot(session, redis, _PanelUp(), bot)
    assert snap.telegram.ok is True
    assert snap.webhook.configured and snap.webhook.pending == 3
    assert snap.webhook.recent_error is True
    assert snap.webhook.last_error_at is not None
    assert snap.webhook.last_error == "Wrong response from the webhook: 502 Bad Gateway"
    assert snap.status == "degraded"  # a recent webhook error degrades the service


async def test_build_snapshot_old_error_is_ok(session) -> None:
    redis = fakeredis.aioredis.FakeRedis(decode_responses=True)
    old = datetime.now(UTC) - timedelta(hours=2)
    snap = await build_snapshot(session, redis, _PanelUp(), _Bot(old, "stale error"))
    assert snap.webhook.recent_error is False
    assert snap.status == "ok"  # an old, resolved error must NOT keep the page degraded


async def test_build_snapshot_no_webhook_error(session) -> None:
    redis = fakeredis.aioredis.FakeRedis(decode_responses=True)
    snap = await build_snapshot(session, redis, _PanelUp(), _Bot(None, None))
    assert snap.telegram.ok and snap.webhook.last_error_at is None
    assert snap.webhook.recent_error is False and snap.status == "ok"
