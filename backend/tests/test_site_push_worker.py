"""P7 — arq worker: site_push_broadcast (fan-out + 404/410 prune) and site_reconcile (self-heal the
webhook fallback). DB-gated; push sends are mocked at the ``gozar.services.push`` seam.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta

import fakeredis.aioredis
from sqlalchemy import select

from gozar.cache.redis import SETTINGS_KEY
from gozar.db.models.push_subscription import PushSubscription
from gozar.db.models.site_device import SiteDevice, SiteDeviceStatus
from gozar.db.repositories.push_subscription import PushSubscriptionRepository
from gozar.db.repositories.site_push_log import SitePushLogRepository
from gozar.remnawave.schemas import PanelUser
from gozar.services import push
from gozar.services.settings_service import SiteSettingKey
from gozar.worker.tasks import site_push_broadcast, site_reconcile

_SETTINGS = {SiteSettingKey.SITE_TRIAL_HOURS: "24"}


async def _cache_redis() -> fakeredis.aioredis.FakeRedis:
    redis = fakeredis.aioredis.FakeRedis(decode_responses=True)
    await redis.set(SETTINGS_KEY, json.dumps(_SETTINGS))
    return redis


# --- site_push_broadcast ------------------------------------------------------------------------


async def test_site_push_broadcast_prunes_only_gone(db_sessions, monkeypatch) -> None:
    async with db_sessions() as s:
        s.add(SiteDevice(uuid="dev-1"))
        await s.flush()
        repo = PushSubscriptionRepository(s)
        for ep in ("https://e/ok", "https://e/gone", "https://e/flap"):
            await repo.upsert(device_uuid="dev-1", endpoint=ep, p256dh="k", auth="a", locale="fa")
        await s.commit()

    async def _fake_send(info, payload):
        ep = info["endpoint"]
        if ep == "https://e/gone":
            return push.PushOutcome.GONE
        if ep == "https://e/flap":
            return push.PushOutcome.FAILED  # transient — must be KEPT
        return push.PushOutcome.SENT

    monkeypatch.setattr(push, "send_push", _fake_send)
    monkeypatch.setattr(push, "PUSH_SEND_DELAY", 0)

    await site_push_broadcast({"sessionmaker": db_sessions}, "Hi", "News", "/")

    async with db_sessions() as s:
        active = {r.endpoint: r.active for r in (await s.scalars(select(PushSubscription))).all()}
    # Only the 404/410 endpoint is deactivated; the transient failure is kept (v1 lesson).
    assert active == {"https://e/ok": True, "https://e/gone": False, "https://e/flap": True}


async def test_site_push_broadcast_no_sessionmaker_is_noop(monkeypatch) -> None:
    called = []
    monkeypatch.setattr(push, "send_push", lambda *a, **k: called.append(1))
    await site_push_broadcast({}, "t", "b", "/")  # missing sessionmaker — guard + return
    assert called == []


# --- site_reconcile -----------------------------------------------------------------------------


class _ReconcilePanel:
    """get_user returns the seeded PanelUser (or None = 404/gone) per username."""

    def __init__(self, users: dict[str, PanelUser | None]) -> None:
        self._users = users
        self.deleted: list[str] = []

    async def get_user(self, username: str) -> PanelUser | None:
        return self._users.get(username)

    async def delete_user_by_username(self, username: str) -> bool:
        self.deleted.append(username)
        return True


def _panel_user(username: str, *, status: str, hours_left: int) -> PanelUser:
    expire = (datetime.now(UTC) + timedelta(hours=hours_left)).isoformat()
    return PanelUser.model_validate({"username": username, "status": status, "expireAt": expire})


async def test_site_reconcile_heals_terminal_leaves_live(db_sessions, monkeypatch) -> None:
    async with db_sessions() as s:
        for uuid, username in (("d-live", "s-live"), ("d-dead", "s-dead"), ("d-exp", "s-exp")):
            s.add(
                SiteDevice(
                    uuid=uuid,
                    status=SiteDeviceStatus.active_config,
                    site_panel_username=username,
                )
            )
        await s.flush()
        await s.commit()

    panel = _ReconcilePanel(
        {
            "s-live": _panel_user("s-live", status="ACTIVE", hours_left=5),  # live -> leave
            "s-dead": None,  # 404 / gone -> terminal
            "s-exp": _panel_user("s-exp", status="EXPIRED", hours_left=-1),  # expired -> terminal
        }
    )
    nudged: list[str] = []

    async def _fake_deliver(sessionmaker, redis, device_uuid, **kwargs):
        nudged.append(device_uuid)

    monkeypatch.setattr(push, "deliver_device_push", _fake_deliver)

    ctx = {"sessionmaker": db_sessions, "panel": panel, "cache_redis": await _cache_redis()}
    await site_reconcile(ctx)

    async with db_sessions() as s:
        status = {
            r.uuid: (r.status, r.site_panel_username)
            for r in (await s.scalars(select(SiteDevice))).all()
        }
    assert status["d-live"] == (SiteDeviceStatus.active_config, "s-live")  # untouched
    assert status["d-dead"] == (SiteDeviceStatus.available, None)  # self-healed
    assert status["d-exp"] == (SiteDeviceStatus.available, None)  # self-healed
    assert set(nudged) == {"d-dead", "d-exp"}  # only the healed devices are nudged
    # Both healed devices attempt a best-effort panel delete; a 404 on the already-gone one is fine.
    assert set(panel.deleted) == {"s-dead", "s-exp"}


async def test_site_reconcile_missing_deps_is_noop(monkeypatch) -> None:
    # No panel/redis in ctx — the task guards and returns without touching anything.
    await site_reconcile({"sessionmaker": object()})


async def test_site_push_broadcast_records_its_outcome(db_sessions, monkeypatch) -> None:
    """The fan-out writes back to its site_push_logs row.

    Without this the admin pressed send and the only trace was a stderr line — no way to know
    whether anything was delivered or how many dead subscriptions were pruned.
    """
    async with db_sessions() as s:
        s.add(SiteDevice(uuid="dev-log"))
        await s.flush()
        repo = PushSubscriptionRepository(s)
        for ep in ("https://e/ok", "https://e/gone"):
            await repo.upsert(device_uuid="dev-log", endpoint=ep, p256dh="k", auth="a", locale="fa")
        log = await SitePushLogRepository(s).create(
            title="t", body="b", url="", locale=None, recipients=2
        )
        log_id = log.id
        await s.commit()

    async def _fake_send(info, payload):
        return (
            push.PushOutcome.GONE if info["endpoint"].endswith("/gone") else push.PushOutcome.SENT
        )

    monkeypatch.setattr(push, "send_push", _fake_send)
    monkeypatch.setattr(push, "PUSH_SEND_DELAY", 0)
    await site_push_broadcast({"sessionmaker": db_sessions}, "t", "b", "", None, log_id)

    async with db_sessions() as s:
        row = await SitePushLogRepository(s).get(log_id)
        assert row is not None
        assert row.status == "done"
        assert (row.sent, row.failed, row.pruned) == (1, 0, 1)
        assert row.finished_at is not None


async def test_site_push_broadcast_targets_one_locale(db_sessions, monkeypatch) -> None:
    async with db_sessions() as s:
        s.add(SiteDevice(uuid="dev-loc"))
        await s.flush()
        repo = PushSubscriptionRepository(s)
        await repo.upsert(
            device_uuid="dev-loc", endpoint="https://e/fa", p256dh="k", auth="a", locale="fa"
        )
        await repo.upsert(
            device_uuid="dev-loc", endpoint="https://e/en", p256dh="k", auth="a", locale="en"
        )
        await s.commit()

    reached: list[str] = []

    async def _fake_send(info, payload):
        reached.append(info["endpoint"])
        return push.PushOutcome.SENT

    monkeypatch.setattr(push, "send_push", _fake_send)
    monkeypatch.setattr(push, "PUSH_SEND_DELAY", 0)
    await site_push_broadcast({"sessionmaker": db_sessions}, "t", "b", "", "en", None)
    assert reached == ["https://e/en"]


async def test_site_push_broadcast_without_a_log_id_still_sends(db_sessions, monkeypatch) -> None:
    """Bookkeeping must never gate delivery — a missing log id sends exactly as before."""
    async with db_sessions() as s:
        s.add(SiteDevice(uuid="dev-nolog"))
        await s.flush()
        await PushSubscriptionRepository(s).upsert(
            device_uuid="dev-nolog", endpoint="https://e/x", p256dh="k", auth="a", locale="fa"
        )
        await s.commit()

    sent: list[str] = []

    async def _fake_send(info, payload):
        sent.append(info["endpoint"])
        return push.PushOutcome.SENT

    monkeypatch.setattr(push, "send_push", _fake_send)
    monkeypatch.setattr(push, "PUSH_SEND_DELAY", 0)
    await site_push_broadcast({"sessionmaker": db_sessions}, "t", "b")
    assert sent == ["https://e/x"]
