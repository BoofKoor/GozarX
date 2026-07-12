"""P7 — Web Push: subscription repo, subscribe/unsubscribe endpoints, send_push outcome mapping,
and the per-device localized nudge fan-out (deliver_device_push).

send_push tests mock pywebpush's ``webpush``; delivery/endpoint tests drive the real app/DB. The
never-mass-delete rule is the focus: a subscription is pruned ONLY on a 404/410.
"""

from __future__ import annotations

import json
from collections.abc import AsyncIterator

import fakeredis.aioredis
import httpx
import pytest_asyncio
from httpx import ASGITransport
from pywebpush import WebPushException
from sqlalchemy import select

from gozar.cache.redis import SETTINGS_KEY
from gozar.config.settings import get_settings
from gozar.db.models.enums import Language
from gozar.db.models.push_subscription import PushSubscription
from gozar.db.models.site_device import SiteDevice
from gozar.db.repositories.push_subscription import PushSubscriptionRepository
from gozar.services import push
from gozar.services.content import ContentService
from gozar.web.app import create_app
from gozar.web.routes.public.push import _SUB_IP_LIMIT

_SETTINGS = {"site_daily_limit_mb": "1024"}


class _Resp:
    def __init__(self, status_code: int) -> None:
        self.status_code = status_code


async def _seed_device(session, uuid: str = "dev-1") -> None:
    session.add(SiteDevice(uuid=uuid))
    await session.flush()


# --- repository ---------------------------------------------------------------------------------


async def test_upsert_dedupes_and_reactivates(session) -> None:
    await _seed_device(session, "dev-1")
    await _seed_device(session, "dev-2")
    repo = PushSubscriptionRepository(session)
    await repo.upsert(
        device_uuid="dev-1", endpoint="https://e/1", p256dh="k", auth="a", locale="fa"
    )
    await repo.deactivate("https://e/1")

    # A re-subscribe on the SAME endpoint re-points the device, refreshes locale, and reactivates.
    await repo.upsert(
        device_uuid="dev-2", endpoint="https://e/1", p256dh="k2", auth="a2", locale="en"
    )
    rows = (await session.scalars(select(PushSubscription))).all()
    assert len(rows) == 1  # deduped on the unique endpoint
    assert rows[0].device_uuid == "dev-2"
    assert rows[0].locale == "en"
    assert rows[0].p256dh == "k2"
    assert rows[0].active is True


async def test_list_active_and_for_device_exclude_inactive(session) -> None:
    await _seed_device(session, "dev-1")
    await _seed_device(session, "dev-2")
    repo = PushSubscriptionRepository(session)
    await repo.upsert(
        device_uuid="dev-1", endpoint="https://e/a", p256dh="k", auth="a", locale="fa"
    )
    await repo.upsert(
        device_uuid="dev-1", endpoint="https://e/b", p256dh="k", auth="a", locale="fa"
    )
    await repo.upsert(
        device_uuid="dev-2", endpoint="https://e/c", p256dh="k", auth="a", locale="fa"
    )
    await repo.deactivate("https://e/b")

    assert {s.endpoint for s in await repo.list_active()} == {"https://e/a", "https://e/c"}
    assert {s.endpoint for s in await repo.list_for_device("dev-1")} == {"https://e/a"}


# --- send_push outcome mapping ------------------------------------------------------------------


def _configure_vapid(monkeypatch) -> None:
    monkeypatch.setenv("VAPID_PRIVATE_KEY", "dummy-key")
    monkeypatch.setenv("VAPID_SUBJECT", "mailto:ops@gozarx.test")
    get_settings.cache_clear()


_INFO = {"endpoint": "https://fcm.googleapis.com/fcm/send/x", "keys": {"p256dh": "k", "auth": "a"}}


async def test_send_push_sent(monkeypatch) -> None:
    _configure_vapid(monkeypatch)
    monkeypatch.setattr(push, "webpush", lambda **kwargs: None)
    assert await push.send_push(_INFO, "{}") is push.PushOutcome.SENT
    get_settings.cache_clear()


async def test_send_push_gone_on_410(monkeypatch) -> None:
    _configure_vapid(monkeypatch)

    def _raise(**kwargs):
        raise WebPushException("gone", response=_Resp(410))

    monkeypatch.setattr(push, "webpush", _raise)
    assert await push.send_push(_INFO, "{}") is push.PushOutcome.GONE
    get_settings.cache_clear()


async def test_send_push_kept_on_transient_500(monkeypatch) -> None:
    _configure_vapid(monkeypatch)

    def _raise(**kwargs):
        raise WebPushException("boom", response=_Resp(500))

    monkeypatch.setattr(push, "webpush", _raise)
    assert await push.send_push(_INFO, "{}") is push.PushOutcome.FAILED
    get_settings.cache_clear()


async def test_send_push_kept_when_no_response(monkeypatch) -> None:
    _configure_vapid(monkeypatch)

    def _raise(**kwargs):
        raise WebPushException("connection reset")  # no .response — transient, keep

    monkeypatch.setattr(push, "webpush", _raise)
    assert await push.send_push(_INFO, "{}") is push.PushOutcome.FAILED
    get_settings.cache_clear()


async def test_send_push_skipped_when_unconfigured(monkeypatch) -> None:
    monkeypatch.setenv("VAPID_PRIVATE_KEY", "")
    monkeypatch.setenv("VAPID_SUBJECT", "")
    get_settings.cache_clear()
    called = []
    monkeypatch.setattr(push, "webpush", lambda **kwargs: called.append(1))
    assert await push.send_push(_INFO, "{}") is push.PushOutcome.FAILED
    assert called == []  # never attempted a send
    get_settings.cache_clear()


# --- deliver_device_push (localized fan-out + prune) --------------------------------------------


async def test_deliver_device_push_localizes_and_prunes(db_sessions, monkeypatch) -> None:
    redis = fakeredis.aioredis.FakeRedis(decode_responses=True)
    async with db_sessions() as s:
        s.add(SiteDevice(uuid="dev-1"))
        await s.flush()
        content = ContentService(s, redis)
        await content.set("site_push_expired_title", Language.fa, "تمام شد")
        await content.set("site_push_expired_title", Language.en, "Ended")
        await content.set("site_push_expired_body", Language.fa, "برگرد")
        await content.set("site_push_expired_body", Language.en, "Come back")
        repo = PushSubscriptionRepository(s)
        await repo.upsert(
            device_uuid="dev-1", endpoint="https://e/fa", p256dh="k", auth="a", locale="fa"
        )
        await repo.upsert(
            device_uuid="dev-1", endpoint="https://e/en", p256dh="k", auth="a", locale="en"
        )
        await s.commit()

    seen: list[tuple[str, str]] = []

    async def _fake_send(info, payload):
        seen.append((info["endpoint"], payload))
        return (
            push.PushOutcome.GONE if info["endpoint"] == "https://e/en" else push.PushOutcome.SENT
        )

    monkeypatch.setattr(push, "send_push", _fake_send)

    await push.deliver_device_push(
        db_sessions,
        redis,
        "dev-1",
        title_key="site_push_expired_title",
        body_key="site_push_expired_body",
        url="/",
        tokens={},
    )

    payloads = {ep: json.loads(p) for ep, p in seen}
    assert payloads["https://e/fa"]["title"] == "تمام شد"  # localized per subscription
    assert payloads["https://e/en"]["title"] == "Ended"
    # Only the 410/GONE endpoint is pruned; the healthy one stays active.
    async with db_sessions() as s:
        rows = {r.endpoint: r.active for r in (await s.scalars(select(PushSubscription))).all()}
    assert rows == {"https://e/fa": True, "https://e/en": False}


# --- endpoints ----------------------------------------------------------------------------------


@pytest_asyncio.fixture
async def env(db_sessions) -> AsyncIterator[tuple[httpx.AsyncClient, object]]:
    get_settings.cache_clear()
    app = create_app()
    app.state.sessionmaker = db_sessions
    app.state.redis = fakeredis.aioredis.FakeRedis(decode_responses=True)
    app.state.panel = None
    app.state.http = None
    await app.state.redis.set(SETTINGS_KEY, json.dumps(_SETTINGS))
    transport = ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://t") as client:
        yield client, app
    get_settings.cache_clear()


_FCM = "https://fcm.googleapis.com/fcm/send/z"
# Well-formed Web Push keys (base64url, realistic lengths) for the endpoint (validated) tests.
_P256 = "x" * 88
_AUTH = "y" * 24


async def test_endpoint_subscribe_then_unsubscribe(env, db_sessions) -> None:
    client, _app = env
    sub = {"endpoint": _FCM, "p256dh": _P256, "auth": _AUTH, "locale": "en"}
    assert (await client.post("/api/public/push/subscribe", json=sub)).json()["ok"] is True
    async with db_sessions() as s:
        row = (await s.scalars(select(PushSubscription))).one()
    assert row.endpoint == _FCM and row.locale == "en" and row.active is True
    assert row.device_uuid is not None  # tied to the minted device

    assert (await client.post("/api/public/push/unsubscribe", json={"endpoint": _FCM})).json()[
        "ok"
    ] is True
    async with db_sessions() as s:
        row = (await s.scalars(select(PushSubscription))).one()
    assert row.active is False


async def test_is_allowed_push_endpoint() -> None:
    ok = [
        "https://fcm.googleapis.com/fcm/send/x",
        "https://updates.push.services.mozilla.com/wpush/v2/x",
        "https://web.push.apple.com/x",
        "https://abc.notify.windows.com/w/",
    ]
    bad = [
        "http://fcm.googleapis.com/x",  # not https
        "https://169.254.169.254/latest/meta-data/",  # cloud metadata (SSRF)
        "https://localhost/x",
        "https://evil.com/x",
        "https://evilgoogleapis.com/x",  # suffix must be a dotted boundary
        "ftp://x",
        "not a url",
    ]
    assert all(push.is_allowed_push_endpoint(e) for e in ok)
    assert not any(push.is_allowed_push_endpoint(e) for e in bad)


async def test_subscribe_rejects_ssrf_endpoint(env) -> None:
    client, _app = env
    ssrf = {
        "endpoint": "https://169.254.169.254/latest/meta-data/",
        "p256dh": _P256,  # well-formed keys, so the 422 can only come from the SSRF endpoint reject
        "auth": _AUTH,
    }
    # Rejected at the API boundary (pydantic 422) before it can ever be stored + POSTed server-side.
    assert (await client.post("/api/public/push/subscribe", json=ssrf)).status_code == 422


async def test_send_push_rejects_non_allowlisted(monkeypatch) -> None:
    _configure_vapid(monkeypatch)
    called = []
    monkeypatch.setattr(push, "webpush", lambda **kwargs: called.append(1))
    info = {"endpoint": "https://evil.com/x", "keys": {"p256dh": "k", "auth": "a"}}
    assert await push.send_push(info, "{}") is push.PushOutcome.FAILED
    assert called == []  # defense-in-depth: never POSTs to a non-push host
    get_settings.cache_clear()


async def test_subscribe_ip_backstop_throttles_cookieless(env) -> None:
    client, _app = env
    # Cookieless clients mint a fresh device each request, so the per-device cap never bites; the
    # per-IP backstop stops the flood after _SUB_IP_LIMIT.
    for i in range(_SUB_IP_LIMIT):
        client.cookies.clear()
        ep = f"https://fcm.googleapis.com/fcm/send/{i}"
        sub = {"endpoint": ep, "p256dh": _P256, "auth": _AUTH}
        assert (await client.post("/api/public/push/subscribe", json=sub)).status_code == 200
    client.cookies.clear()
    flood = {"endpoint": "https://fcm.googleapis.com/fcm/send/last", "p256dh": _P256, "auth": _AUTH}
    assert (await client.post("/api/public/push/subscribe", json=flood)).status_code == 429
