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
from gozar.db.models.push_subscription import PushSubscription
from gozar.db.models.site_claim import SiteClaim
from gozar.db.models.site_device import SiteDevice
from gozar.db.models.site_message import SiteMessage
from gozar.db.models.site_reward import SiteReward
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
    # trial_hours is floored to 1 (never 0)
    assert (await site_client.put("/api/admin/site/settings/", json={"trial_hours": 0})).json()[
        "trial_hours"
    ] == 1
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


async def _subscribe(db_sessions, *, endpoint: str, locale: str = "fa") -> None:
    async with db_sessions() as s:
        s.add(SiteDevice(uuid=f"dev-{endpoint}"))
        await s.flush()
        s.add(
            PushSubscription(
                device_uuid=f"dev-{endpoint}",
                endpoint=endpoint,
                p256dh="k",
                auth="a",
                locale=locale,
            )
        )
        await s.commit()


async def test_push_enqueues_worker_job(db_sessions, monkeypatch) -> None:
    monkeypatch.setenv("ADMIN_JWT_SECRET", _SECRET)
    monkeypatch.setenv("ADMIN_USERNAME", "root")
    get_settings.cache_clear()
    await _subscribe(db_sessions, endpoint="e1")
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
        log_id = r.json()["log_id"]
        # The job carries the locale filter and the log id so the worker can write the outcome back.
        assert arq.jobs == [("site_push_broadcast", ("hi", "there", "/status", None, log_id))]

        # A row exists immediately, BEFORE the worker runs — a lost job stays visible as "queued"
        # rather than vanishing without a trace.
        history = (await c.get("/api/admin/site/push/history")).json()
        assert len(history) == 1
        assert history[0]["status"] == "queued"
        assert history[0]["recipients"] == 1
        assert history[0]["sent"] == 0
    get_settings.cache_clear()


async def test_push_refuses_an_empty_audience(db_sessions, monkeypatch) -> None:
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
        r = await c.post("/api/admin/site/push/", json={"title": "hi", "body": "there"})
        # "queued to 0 devices" is exactly the silent nothing this section is meant to stop.
        assert r.status_code == 409
    assert arq.jobs == []
    get_settings.cache_clear()


async def test_push_targets_one_locale(db_sessions, monkeypatch) -> None:
    monkeypatch.setenv("ADMIN_JWT_SECRET", _SECRET)
    monkeypatch.setenv("ADMIN_USERNAME", "root")
    get_settings.cache_clear()
    await _subscribe(db_sessions, endpoint="fa1", locale="fa")
    await _subscribe(db_sessions, endpoint="fa2", locale="fa")
    await _subscribe(db_sessions, endpoint="en1", locale="en")
    arq = _FakeArq()
    app = _build_app(db_sessions, arq=arq)
    token = create_access("root")
    async with httpx.AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://t",
        headers={"Authorization": f"Bearer {token}"},
    ) as c:
        audience = (await c.get("/api/admin/site/push/")).json()
        assert audience["recipients"] == 3
        assert {r["locale"]: r["count"] for r in audience["by_locale"]} == {"fa": 2, "en": 1}

        r = await c.post("/api/admin/site/push/", json={"title": "hi", "body": "b", "locale": "en"})
        assert r.status_code == 200
        assert r.json()["recipients"] == 1  # the echo matches what will actually be sent
        assert arq.jobs[0][1][4 - 1] == "en"

        assert (
            await c.post("/api/admin/site/push/", json={"title": "h", "body": "b", "locale": "ru"})
        ).status_code == 422
    get_settings.cache_clear()


async def test_push_rejects_an_offsite_url(db_sessions, monkeypatch) -> None:
    monkeypatch.setenv("ADMIN_JWT_SECRET", _SECRET)
    monkeypatch.setenv("ADMIN_USERNAME", "root")
    get_settings.cache_clear()
    await _subscribe(db_sessions, endpoint="u1")
    arq = _FakeArq()
    app = _build_app(db_sessions, arq=arq)
    token = create_access("root")
    async with httpx.AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://t",
        headers={"Authorization": f"Bearer {token}"},
    ) as c:
        # The value reaches every subscriber's notificationclick handler, so it must be an in-site
        # path or a plain https address — never a javascript:, http: or protocol-relative URL.
        for bad in ("javascript:alert(1)", "http://evil.example", "//evil.example", "data:x"):
            r = await c.post("/api/admin/site/push/", json={"title": "h", "body": "b", "url": bad})
            assert r.status_code == 422, f"{bad!r} should have been rejected"
        for good in ("/status", "https://gozarx.example/status", ""):
            r = await c.post("/api/admin/site/push/", json={"title": "h", "body": "b", "url": good})
            assert r.status_code == 200, f"{good!r} should have been accepted"
    get_settings.cache_clear()


async def test_site_stats_funnel(site_client: httpx.AsyncClient, db_sessions) -> None:
    empty = (await site_client.get("/api/admin/site/stats/")).json()
    assert empty["total_devices"] == 0 and empty["conversion_pct"] == 0.0
    # claims_series is zero-filled to exactly range_days ascending points (continuous time axis).
    assert empty["range_days"] == 14
    assert len(empty["claims_series"]) == 14
    assert all(pt["count"] == 0 for pt in empty["claims_series"])

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


async def test_site_analytics_empty(site_client: httpx.AsyncClient) -> None:
    body = (await site_client.get("/api/admin/site/stats/analytics")).json()
    assert body["dau"] == 0 and body["mau"] == 0 and body["stickiness_pct"] == 0.0
    assert body["reward_economy"] == [] and body["streak_distribution"] == {}
    assert body["push"] == {"active": 0, "inactive": 0, "by_locale": []}
    assert body["abuse"] == {"top_ip_buckets": [], "shared_fingerprint_devices": 0}


async def test_site_analytics_aggregations(site_client: httpx.AsyncClient, db_sessions) -> None:
    async with db_sessions() as s:
        s.add_all(
            [
                SiteDevice(uuid="d1", streak_count=5, ip_bucket="ipA", fingerprint_hash="fpX"),
                SiteDevice(uuid="d2", streak_count=0, ip_bucket="ipA", fingerprint_hash="fpX"),
                SiteDevice(uuid="d3", streak_count=8, ip_bucket="ipB", fingerprint_hash="fpY"),
            ]
        )
        await s.flush()
        s.add_all(
            [
                SiteClaim(device_uuid="d1", location="DE"),  # provision
                SiteClaim(device_uuid="d2", location="NL"),  # provision
                SiteReward(device_uuid="d1", reward_type="pwa", amount_mb=200),
                SiteReward(device_uuid="d2", reward_type="pwa", amount_mb=200),
                SiteReward(device_uuid="d1", reward_type="push", amount_mb=200),
                PushSubscription(
                    device_uuid="d1", endpoint="e1", p256dh="k", auth="a", locale="fa"
                ),
                PushSubscription(
                    device_uuid="d2", endpoint="e2", p256dh="k", auth="a", locale="en", active=False
                ),
            ]
        )
        await s.commit()

    body = (await site_client.get("/api/admin/site/stats/analytics")).json()
    assert body["dau"] == 2 and body["wau"] == 2 and body["mau"] == 2  # d1, d2 provisioned
    assert body["stickiness_pct"] == 100.0
    econ = {r["type"]: (r["grants"], r["total_mb"]) for r in body["reward_economy"]}
    assert econ == {"pwa": (2, 400), "push": (1, 200)}
    assert body["streak_distribution"] == {"0": 1, "3-6": 1, "7+": 1}  # d2=0, d1=5, d3=8
    assert body["push"]["active"] == 1 and body["push"]["inactive"] == 1
    assert body["push"]["by_locale"] == [{"label": "fa", "count": 1}]  # active only
    assert body["abuse"]["top_ip_buckets"] == [{"label": "ipA", "count": 2}]
    assert body["abuse"]["shared_fingerprint_devices"] == 2  # d1 & d2 share fpX


# --- location validation (the wizard used to be a hole straight through the settings check) ---


async def test_setup_rejects_a_location_the_squad_does_not_serve(
    site_client: httpx.AsyncClient,
) -> None:
    r = await site_client.post(
        "/api/admin/site/setup/",
        json={"trial_squad": "sq-1", "locations": ["Germany", "Narnia"]},
    )
    assert r.status_code == 400
    # The message must name BOTH the offending value and what is actually available, so a typo is
    # fixable without opening the panel.
    assert "Narnia" in r.json()["detail"]
    assert "Germany" in r.json()["detail"]
    # Nothing was persisted — the squad is still unset.
    assert (await site_client.get("/api/admin/site/setup/status")).json()["completed"] is False


async def test_setup_accepts_a_valid_subset(site_client: httpx.AsyncClient) -> None:
    r = await site_client.post(
        "/api/admin/site/setup/", json={"trial_squad": "sq-1", "locations": ["Finland"]}
    )
    assert r.status_code == 200
    assert (await site_client.get("/api/admin/site/settings/")).json()["locations"] == ["Finland"]


async def test_settings_rejects_a_popular_location_outside_the_list(
    site_client: httpx.AsyncClient,
) -> None:
    await site_client.post(
        "/api/admin/site/setup/", json={"trial_squad": "sq-1", "locations": ["Germany"]}
    )
    r = await site_client.put("/api/admin/site/settings/", json={"popular_location": "Finland"})
    assert r.status_code == 400
    assert "Finland" in r.json()["detail"]
    assert (await site_client.get("/api/admin/site/settings/")).json()["popular_location"] in (
        None,
        "",
    )


async def test_settings_validates_popular_against_the_list_in_the_same_request(
    site_client: httpx.AsyncClient,
) -> None:
    await site_client.post(
        "/api/admin/site/setup/", json={"trial_squad": "sq-1", "locations": ["Germany"]}
    )
    # Swapping the list and the star in ONE request must validate against the NEW list, not the
    # stored one — otherwise a perfectly consistent edit is rejected.
    r = await site_client.put(
        "/api/admin/site/settings/",
        json={"locations": ["Finland"], "popular_location": "Finland"},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["locations"] == ["Finland"] and body["popular_location"] == "Finland"


async def test_settings_allows_clearing_the_popular_location(
    site_client: httpx.AsyncClient,
) -> None:
    await site_client.post(
        "/api/admin/site/setup/", json={"trial_squad": "sq-1", "locations": ["Germany"]}
    )
    await site_client.put("/api/admin/site/settings/", json={"popular_location": "Germany"})
    r = await site_client.put("/api/admin/site/settings/", json={"popular_location": ""})
    assert r.status_code == 200
    assert r.json()["popular_location"] in (None, "")


# --- the stats range control has to move the WHOLE page, analytics band included ---


async def test_site_analytics_is_windowed(site_client: httpx.AsyncClient) -> None:
    body = (await site_client.get("/api/admin/site/stats/analytics?days=7")).json()
    assert body["range_days"] == 7
    # an unsupported window snaps back to the default rather than silently using "all time"
    assert (await site_client.get("/api/admin/site/stats/analytics?days=999")).json()[
        "range_days"
    ] == 14
    assert (await site_client.get("/api/admin/site/stats/analytics?days=90")).json()[
        "range_days"
    ] == 90


# --- landing slugs end up in a public URL (/l/{slug}) ---


async def test_landing_rejects_an_unusable_slug(site_client: httpx.AsyncClient) -> None:
    for bad in ("has spaces", "Upper-Case", "کانفیگ-رایگان", "trailing-", "double--hyphen"):
        r = await site_client.post(
            "/api/admin/site/pages/", json={"slug": bad, "locale": "fa", "title": "t"}
        )
        assert r.status_code == 422, f"{bad!r} should have been rejected"


async def test_landing_accepts_a_url_safe_slug(site_client: httpx.AsyncClient) -> None:
    r = await site_client.post(
        "/api/admin/site/pages/",
        json={"slug": "free-v2ray-config", "locale": "fa", "title": "کانفیگ رایگان"},
    )
    assert r.status_code == 201
    assert r.json()["slug"] == "free-v2ray-config"


async def test_landing_update_also_validates_the_slug(site_client: httpx.AsyncClient) -> None:
    created = (
        await site_client.post(
            "/api/admin/site/pages/", json={"slug": "ok-slug", "locale": "fa", "title": "t"}
        )
    ).json()
    r = await site_client.put(
        f"/api/admin/site/pages/{created['id']}",
        json={"slug": "not ok", "locale": "fa", "title": "t"},
    )
    assert r.status_code == 422


# --- inbox: search, locale filter, unread toggle, delete ---


async def _seed_messages(db_sessions) -> None:
    async with db_sessions() as s:
        s.add_all(
            [
                SiteMessage(subject="سوال دربارهٔ آلمان", body="سلام", locale="fa"),
                SiteMessage(subject="Billing question", body="hello there", locale="en"),
                SiteMessage(
                    subject="spam", body="buy now", locale="fa", reply_handle="a@b.com", read=True
                ),
            ]
        )
        await s.commit()


async def test_inbox_search_matches_subject_body_and_handle(
    site_client: httpx.AsyncClient, db_sessions
) -> None:
    await _seed_messages(db_sessions)
    for query, expected in (("آلمان", 1), ("hello", 1), ("a@b.com", 1), ("nothing", 0)):
        body = (await site_client.get(f"/api/admin/site/inbox/?search={query}")).json()
        assert len(body["items"]) == expected, query
        # The pager must divide by the FILTERED count, not the total — otherwise a search shows
        # phantom empty pages past the real end.
        assert body["matching"] == expected
        assert body["total"] == 3


async def test_inbox_filters_by_locale(site_client: httpx.AsyncClient, db_sessions) -> None:
    await _seed_messages(db_sessions)
    body = (await site_client.get("/api/admin/site/inbox/?locale=en")).json()
    assert [m["subject"] for m in body["items"]] == ["Billing question"]
    assert body["matching"] == 1


async def test_inbox_can_mark_a_message_unread_again(
    site_client: httpx.AsyncClient, db_sessions
) -> None:
    await _seed_messages(db_sessions)
    read = next(
        m for m in (await site_client.get("/api/admin/site/inbox/")).json()["items"] if m["read"]
    )
    r = await site_client.post(f"/api/admin/site/inbox/{read['id']}/unread")
    assert r.status_code == 200 and r.json()["read"] is False
    # Opening a message marks it read automatically, so "leave it for later" needs this.
    assert (await site_client.get("/api/admin/site/inbox/")).json()["unread"] == 3


async def test_inbox_delete_removes_the_message(
    site_client: httpx.AsyncClient, db_sessions
) -> None:
    await _seed_messages(db_sessions)
    first = (await site_client.get("/api/admin/site/inbox/")).json()["items"][0]
    assert (await site_client.delete(f"/api/admin/site/inbox/{first['id']}")).status_code == 204
    assert (await site_client.get("/api/admin/site/inbox/")).json()["total"] == 2
    assert (await site_client.delete(f"/api/admin/site/inbox/{first['id']}")).status_code == 404
