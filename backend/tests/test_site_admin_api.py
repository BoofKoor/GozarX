"""P9b — website ('site') admin API integration (DB-gated).

Drives the real ``/api/admin/site/*`` routes with httpx + ASGITransport, mirroring
``test_admin_api.py``: ``app.state`` is wired directly (fresh test schema, fakeredis, a stub panel),
so no lifespan / real Redis is needed. Skipped without ``TEST_DATABASE_URL``.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from types import SimpleNamespace

import fakeredis.aioredis
import httpx
import pytest_asyncio
from httpx import ASGITransport

from gozar.config.settings import get_settings
from gozar.db.models.site_claim import SiteClaim
from gozar.db.models.site_device import SiteDevice
from gozar.db.models.site_message import SiteMessage
from gozar.web.app import create_app
from gozar.web.auth.jwt import create_access

_SECRET = "test-admin-secret-0123456789-abcdef-ghijkl"  # >=32 bytes for PyJWT


class _StubPanel:
    async def list_internal_squads(self) -> list[SimpleNamespace]:
        return [SimpleNamespace(uuid="sq-1", name="Squad One")]

    async def squad_location_names(self, squad_uuid: str) -> list[str]:
        return ["Germany", "Finland"]

    async def system_stats(self):
        return None


class _FakeArq:
    def __init__(self) -> None:
        self.jobs: list = []

    async def enqueue_job(self, name: str, *args: object) -> None:
        self.jobs.append((name, args))


def _build_app(db_sessions, *, arq: object | None = None):
    app = create_app()
    app.state.sessionmaker = db_sessions
    app.state.redis = fakeredis.aioredis.FakeRedis(decode_responses=True)
    app.state.panel = _StubPanel()
    app.state.arq = arq
    return app


@pytest_asyncio.fixture
async def site_client(db_sessions, monkeypatch) -> AsyncIterator[httpx.AsyncClient]:
    monkeypatch.setenv("ADMIN_JWT_SECRET", _SECRET)
    monkeypatch.setenv("ADMIN_USERNAME", "root")
    get_settings.cache_clear()
    app = _build_app(db_sessions, arq=None)  # arq None -> push POST returns 503 unless overridden
    token = create_access("root")
    async with httpx.AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://t",
        headers={"Authorization": f"Bearer {token}"},
    ) as c:
        yield c
    get_settings.cache_clear()


async def test_site_routes_require_auth(site_client: httpx.AsyncClient) -> None:
    r = await site_client.get("/api/admin/site/settings/", headers={"Authorization": ""})
    assert r.status_code == 401


async def test_site_setup_derives_locations_from_squad(site_client: httpx.AsyncClient) -> None:
    assert (await site_client.get("/api/admin/site/setup/status")).json()["completed"] is False
    # the wizard's picker options come from the squad's remark names
    assert (await site_client.get("/api/admin/site/setup/locations?squad=sq-1")).json() == [
        "Germany",
        "Finland",
    ]
    # empty allowlist -> derive every squad location by NAME
    r = await site_client.post("/api/admin/site/setup/", json={"trial_squad": "sq-1"})
    assert r.status_code == 200 and r.json()["completed"] is True
    settings = (await site_client.get("/api/admin/site/settings/")).json()
    assert settings["trial_squad"] == "sq-1"
    assert settings["locations"] == ["Germany", "Finland"]


async def test_site_setup_respects_explicit_locations(site_client: httpx.AsyncClient) -> None:
    await site_client.post(
        "/api/admin/site/setup/", json={"trial_squad": "sq-1", "locations": ["Germany"]}
    )
    assert (await site_client.get("/api/admin/site/settings/")).json()["locations"] == ["Germany"]


async def test_site_settings_update_and_refresh_locations(site_client: httpx.AsyncClient) -> None:
    r = await site_client.put(
        "/api/admin/site/settings/", json={"daily_limit_mb": 2048, "streak_days": 5}
    )
    assert r.status_code == 200
    assert r.json()["daily_limit_mb"] == 2048 and r.json()["streak_days"] == 5
    # negatives are clamped to 0
    assert (
        await site_client.put("/api/admin/site/settings/", json={"referral_reward_mb": -9})
    ).json()["referral_reward_mb"] == 0
    # refresh-locations needs a squad; 400 before setup
    assert (await site_client.post("/api/admin/site/settings/refresh-locations")).status_code == 400
    await site_client.post("/api/admin/site/setup/", json={"trial_squad": "sq-1"})
    r = await site_client.post("/api/admin/site/settings/refresh-locations")
    assert r.status_code == 200 and r.json()["locations"] == ["Germany", "Finland"]


async def test_landing_crud_flow(site_client: httpx.AsyncClient) -> None:
    payload = {"slug": "free-v2ray", "locale": "fa", "title": "کانفیگ رایگان"}
    created = await site_client.post("/api/admin/site/pages/", json=payload)
    assert created.status_code == 201
    page_id = created.json()["id"]
    assert created.json()["published"] is True

    # duplicate (slug, locale) -> 409; bad locale -> 422
    assert (await site_client.post("/api/admin/site/pages/", json=payload)).status_code == 409
    assert (
        await site_client.post(
            "/api/admin/site/pages/", json={"slug": "x", "locale": "ru", "title": "t"}
        )
    ).status_code == 422

    # the same slug in en is allowed
    assert (
        await site_client.post(
            "/api/admin/site/pages/", json={"slug": "free-v2ray", "locale": "en", "title": "Free"}
        )
    ).status_code == 201
    assert len((await site_client.get("/api/admin/site/pages/")).json()) == 2
    assert len((await site_client.get("/api/admin/site/pages/?locale=fa")).json()) == 1

    # update + get
    upd = await site_client.put(
        f"/api/admin/site/pages/{page_id}",
        json={**payload, "title": "عنوان نو", "published": False},
    )
    assert upd.status_code == 200 and upd.json()["title"] == "عنوان نو"
    assert (await site_client.get(f"/api/admin/site/pages/{page_id}")).json()["published"] is False

    # delete -> 204 then 404
    assert (await site_client.delete(f"/api/admin/site/pages/{page_id}")).status_code == 204
    assert (await site_client.get(f"/api/admin/site/pages/{page_id}")).status_code == 404


async def test_inbox_list_and_mark_read(site_client: httpx.AsyncClient, db_sessions) -> None:
    async with db_sessions() as s:
        s.add_all(
            [
                SiteMessage(
                    subject="s1", body="b1", reply_handle=None, locale="fa", device_uuid=None
                ),
                SiteMessage(
                    subject="s2", body="b2", reply_handle="me@x", locale="en", device_uuid=None
                ),
            ]
        )
        await s.commit()

    listing = (await site_client.get("/api/admin/site/inbox/")).json()
    assert listing["total"] == 2 and listing["unread"] == 2
    newest = listing["items"][0]
    assert newest["subject"] == "s2"

    r = await site_client.post(f"/api/admin/site/inbox/{newest['id']}/read")
    assert r.status_code == 200 and r.json()["read"] is True
    assert (await site_client.get("/api/admin/site/inbox/")).json()["unread"] == 1
    assert (await site_client.get("/api/admin/site/inbox/?unread=true")).json()["total"] == 2
    assert len((await site_client.get("/api/admin/site/inbox/?unread=true")).json()["items"]) == 1
    assert (await site_client.post("/api/admin/site/inbox/999999/read")).status_code == 404


async def test_push_audience_and_missing_worker(site_client: httpx.AsyncClient) -> None:
    assert (await site_client.get("/api/admin/site/push/")).json()["recipients"] == 0
    # arq is None on this app -> the producer refuses rather than running inline
    r = await site_client.post("/api/admin/site/push/", json={"title": "t", "body": "b"})
    assert r.status_code == 503


async def test_push_enqueues_worker_job(db_sessions, monkeypatch) -> None:
    monkeypatch.setenv("ADMIN_JWT_SECRET", _SECRET)
    monkeypatch.setenv("ADMIN_USERNAME", "root")
    get_settings.cache_clear()
    arq = _FakeArq()
    app = _build_app(db_sessions, arq=arq)
    token = create_access("root")
    async with httpx.AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://t",
        headers={"Authorization": f"Bearer {token}"},
    ) as c:
        r = await c.post(
            "/api/admin/site/push/", json={"title": "hi", "body": "there", "url": "/status"}
        )
        assert r.status_code == 200 and r.json()["queued"] is True
    assert arq.jobs == [("site_push_broadcast", ("hi", "there", "/status"))]
    get_settings.cache_clear()


async def test_site_stats_funnel(site_client: httpx.AsyncClient, db_sessions) -> None:
    empty = (await site_client.get("/api/admin/site/stats/")).json()
    assert empty["total_devices"] == 0 and empty["conversion_pct"] == 0.0
    assert empty["range_days"] == 14 and empty["claims_series"] == []

    async with db_sessions() as s:
        s.add_all([SiteDevice(uuid="d1"), SiteDevice(uuid="d2"), SiteDevice(uuid="d3")])
        await s.flush()
        s.add_all(
            [
                SiteClaim(device_uuid="d1", location="Germany"),
                SiteClaim(device_uuid="d1", location="Germany"),
                SiteClaim(device_uuid="d2", location="Finland"),
            ]
        )
        await s.commit()

    body = (await site_client.get("/api/admin/site/stats/")).json()
    assert body["total_devices"] == 3
    assert body["devices_claimed"] == 2  # d1, d2
    assert body["conversion_pct"] == round(2 / 3 * 100, 1)
    assert {x["label"]: x["count"] for x in body["top_locations"]} == {"Germany": 2, "Finland": 1}
    assert body["status_counts"].get("available") == 3
