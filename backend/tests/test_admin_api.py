"""Admin API integration (DB-gated): setup wizard, settings CRUD, dashboard stats.

Drives the real `/api/admin/*` routes with httpx + ASGITransport. ``app.state`` is set directly
(sessionmaker from the fresh test schema, fakeredis, a stub panel) so no lifespan / real Redis is
needed. Skipped without ``TEST_DATABASE_URL`` (the ``db_sessions`` fixture skips).
"""

from __future__ import annotations

import json
from collections.abc import AsyncIterator
from types import SimpleNamespace

import fakeredis.aioredis
import httpx
import pytest_asyncio
from httpx import ASGITransport

from gozar.cache.redis import HEALTH_HISTORY_KEY
from gozar.config.settings import get_settings
from gozar.db.models.config_log import ConfigLog
from gozar.db.models.enums import Language, UserStatus
from gozar.db.models.user import User
from gozar.remnawave.schemas import SystemStats
from gozar.web.app import create_app
from gozar.web.auth.jwt import create_access

_SECRET = "test-admin-secret-0123456789-abcdef-ghijkl"  # ≥32 bytes for PyJWT


class _StubPanel:
    async def list_internal_squads(self) -> list[SimpleNamespace]:
        return [
            SimpleNamespace(uuid="sq-1", name="Squad One"),
            SimpleNamespace(uuid="sq-2", name="Squad Two"),
        ]

    async def system_stats(self) -> SystemStats | None:
        return None  # panel unreachable in tests -> dashboard falls back to the DB active count

    async def get_user(self, username: str):
        return None  # no live panel account in tests -> reclaim/ban revoke is a no-op

    async def delete_user(self, uuid: str) -> bool:
        return True


@pytest_asyncio.fixture
async def admin_client(db_sessions, monkeypatch) -> AsyncIterator[httpx.AsyncClient]:
    monkeypatch.setenv("ADMIN_JWT_SECRET", _SECRET)
    monkeypatch.setenv("ADMIN_USERNAME", "root")
    get_settings.cache_clear()
    app = create_app()
    app.state.sessionmaker = db_sessions
    app.state.redis = fakeredis.aioredis.FakeRedis(decode_responses=True)
    app.state.panel = _StubPanel()
    token = create_access("root")
    transport = ASGITransport(app=app)
    async with httpx.AsyncClient(
        transport=transport, base_url="http://t", headers={"Authorization": f"Bearer {token}"}
    ) as c:
        yield c
    get_settings.cache_clear()


async def test_setup_starts_incomplete(admin_client: httpx.AsyncClient) -> None:
    r = await admin_client.get("/api/admin/setup/status")
    assert r.status_code == 200
    assert r.json()["completed"] is False


async def test_setup_lists_squads(admin_client: httpx.AsyncClient) -> None:
    r = await admin_client.get("/api/admin/setup/squads")
    assert r.status_code == 200
    assert {s["uuid"] for s in r.json()} == {"sq-1", "sq-2"}


async def test_setup_complete_persists_and_flips_status(admin_client: httpx.AsyncClient) -> None:
    r = await admin_client.post(
        "/api/admin/setup/",
        json={"trial_squad": "sq-1", "locations": ["NL", "DE"], "daily_limit_mb": 2048},
    )
    assert r.status_code == 200 and r.json()["completed"] is True
    assert (await admin_client.get("/api/admin/setup/status")).json()["completed"] is True
    settings = (await admin_client.get("/api/admin/settings/")).json()
    assert settings["trial_squad"] == "sq-1"
    assert settings["locations"] == ["NL", "DE"]
    assert settings["daily_limit_mb"] == 2048


async def test_settings_put_partial_update(admin_client: httpx.AsyncClient) -> None:
    r = await admin_client.put(
        "/api/admin/settings/", json={"ads_enabled": True, "trial_hours": 48}
    )
    assert r.status_code == 200
    body = r.json()
    assert body["ads_enabled"] is True
    assert body["trial_hours"] == 48


async def test_settings_ad_button_round_trip(admin_client: httpx.AsyncClient) -> None:
    # Fresh schema -> the ad button is off with blank text/url/emoji until the admin sets it.
    before = (await admin_client.get("/api/admin/settings/")).json()
    assert before["ad_button_enabled"] is False
    assert before["ad_button_text"] == ""
    assert before["ad_button_url"] == ""
    assert before["ad_button_emoji_id"] == ""

    r = await admin_client.put(
        "/api/admin/settings/",
        json={
            "ad_button_enabled": True,
            "ad_button_text": "  کانال ما  ",  # trimmed on save
            "ad_button_url": "https://t.me/example",
            "ad_button_emoji_id": "5368324170671202286",
        },
    )
    assert r.status_code == 200
    body = r.json()
    assert body["ad_button_enabled"] is True
    assert body["ad_button_text"] == "کانال ما"
    assert body["ad_button_url"] == "https://t.me/example"
    assert body["ad_button_emoji_id"] == "5368324170671202286"
    # and it persists across a fresh read
    assert (await admin_client.get("/api/admin/settings/")).json()["ad_button_enabled"] is True


async def test_dashboard_stats_shape_on_empty_db(admin_client: httpx.AsyncClient) -> None:
    r = await admin_client.get("/api/admin/dashboard/stats")
    assert r.status_code == 200
    body = r.json()
    for key in ("total_users", "available", "active", "banned", "configs_today", "referrals"):
        assert body[key] == 0
    assert body["claims_series"] == []
    # richer payload defaults: online -> active fallback (0), panel unreachable, default range
    assert body["online_now"] == 0
    assert body["range_days"] == 14
    assert body["panel_online"] is False
    for key in ("new_today", "new_this_week", "conversion_pct", "avg_referrals", "nodes_online"):
        assert body[key] == 0
    assert body["panel_status_counts"] == {}
    for key in ("signups_series", "languages", "top_locations", "top_referrers"):
        assert body[key] == []


async def test_dashboard_stats_aggregations(admin_client: httpx.AsyncClient, db_sessions) -> None:
    async with db_sessions() as s:
        s.add_all(
            [
                User(telegram_id=11, language=Language.fa, referral_count=5),
                User(telegram_id=12, language=Language.fa, referral_count=0),
                User(telegram_id=13, language=Language.en, referral_count=2),
            ]
        )
        await s.flush()  # users must exist before config_logs (FK; no ORM rel to order them)
        s.add_all(
            [
                ConfigLog(user_id=11, location="Germany"),
                ConfigLog(user_id=11, location="Germany"),
                ConfigLog(user_id=13, location="Finland"),
            ]
        )
        await s.commit()

    body = (await admin_client.get("/api/admin/dashboard/stats")).json()
    assert body["total_users"] == 3 and body["referrals"] == 7
    assert {x["label"]: x["count"] for x in body["languages"]} == {"fa": 2, "en": 1}
    assert {x["label"]: x["count"] for x in body["top_locations"]} == {"Germany": 2, "Finland": 1}
    assert [(r["telegram_id"], r["referral_count"]) for r in body["top_referrers"]] == [
        (11, 5),
        (13, 2),
    ]  # only referrers with count > 0, biggest first
    assert body["new_today"] == 3  # all three just created
    assert body["conversion_pct"] == round(2 / 3 * 100, 1)  # users 11 & 13 claimed, of 3 total
    assert body["avg_referrals"] == round(7 / 3, 2)


async def test_dashboard_range_clamped(admin_client: httpx.AsyncClient) -> None:
    assert (await admin_client.get("/api/admin/dashboard/stats?days=7")).json()["range_days"] == 7
    assert (await admin_client.get("/api/admin/dashboard/stats?days=30")).json()["range_days"] == 30
    # an unsupported window snaps back to the 14-day default (never an arbitrary range)
    r = await admin_client.get("/api/admin/dashboard/stats?days=999")
    assert r.json()["range_days"] == 14


async def test_dashboard_surfaces_panel_system_stats(db_sessions, monkeypatch) -> None:
    monkeypatch.setenv("ADMIN_JWT_SECRET", _SECRET)
    monkeypatch.setenv("ADMIN_USERNAME", "root")
    get_settings.cache_clear()
    app = create_app()
    app.state.sessionmaker = db_sessions
    app.state.redis = fakeredis.aioredis.FakeRedis(decode_responses=True)

    class _Panel(_StubPanel):  # a reachable panel reports live online + status counts
        async def system_stats(self) -> SystemStats:
            return SystemStats(
                online_now=4,
                online_last_day=30,
                online_last_week=70,
                never_online=1,
                status_counts={"ACTIVE": 9, "EXPIRED": 2},
                total_users=11,
                nodes_online=2,
                total_traffic_bytes=9876543210,
            )

    app.state.panel = _Panel()
    token = create_access("root")
    async with httpx.AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://t",
        headers={"Authorization": f"Bearer {token}"},
    ) as c:
        body = (await c.get("/api/admin/dashboard/stats")).json()
    assert body["online_now"] == 4 and body["panel_online"] is True
    assert body["online_last_day"] == 30 and body["never_online"] == 1
    assert body["panel_status_counts"] == {"ACTIVE": 9, "EXPIRED": 2}
    assert body["total_traffic_bytes"] == 9876543210 and body["nodes_online"] == 2
    get_settings.cache_clear()


async def test_protected_route_rejects_missing_token(admin_client: httpx.AsyncClient) -> None:
    # Same app, but strip the Authorization header for this one call.
    r = await admin_client.get("/api/admin/settings/", headers={"Authorization": ""})
    assert r.status_code == 401


# --- buttons editor ----------------------------------------------------------------------------
async def test_buttons_list_includes_catalogue_with_criticals(
    admin_client: httpx.AsyncClient,
) -> None:
    r = await admin_client.get("/api/admin/buttons/")
    assert r.status_code == 200
    items = r.json()
    keys = {i["key"] for i in items}
    assert {"menu_config", "back", "admin_stats"} <= keys
    backs = [i for i in items if i["key"] == "back"]
    assert backs and all(i["is_critical"] for i in backs)  # shared chrome, all critical
    mc = next(i for i in items if i["key"] == "menu_config")
    assert mc["customized"] is False
    assert mc["effective_label"]["fa"] == mc["default_label"]["fa"]


async def test_buttons_update_appearance(admin_client: httpx.AsyncClient) -> None:
    r = await admin_client.put(
        "/api/admin/buttons/menu_config", json={"labels": {"fa": "سفارشی"}, "is_visible": True}
    )
    assert r.status_code == 200
    mc = next(i for i in r.json() if i["key"] == "menu_config")
    assert mc["effective_label"]["fa"] == "سفارشی"
    assert mc["customized"] is True


async def test_buttons_cannot_hide_critical(admin_client: httpx.AsyncClient) -> None:
    r = await admin_client.put("/api/admin/buttons/back", json={"is_visible": False})
    assert r.status_code == 422


async def test_buttons_reset(admin_client: httpx.AsyncClient) -> None:
    await admin_client.put(
        "/api/admin/buttons/menu_help", json={"labels": {"en": "X"}, "is_visible": True}
    )
    r = await admin_client.post("/api/admin/buttons/menu_help/reset")
    assert r.status_code == 200
    mh = next(i for i in r.json() if i["key"] == "menu_help")
    assert mh["customized"] is False


async def test_buttons_reorder(admin_client: httpx.AsyncClient) -> None:
    r = await admin_client.post(
        "/api/admin/buttons/reorder",
        json={"items": [{"key": "menu_help", "row_index": 0, "position": 1}]},
    )
    assert r.status_code == 200
    mh = next(i for i in r.json() if i["key"] == "menu_help" and i["screen"] == "main_menu")
    assert mh["effective_row"] == 0 and mh["effective_position"] == 1


async def test_buttons_set_and_clear_style(admin_client: httpx.AsyncClient) -> None:
    r = await admin_client.put(
        "/api/admin/buttons/menu_config", json={"is_visible": True, "style": "success"}
    )
    assert r.status_code == 200
    mc = next(i for i in r.json() if i["key"] == "menu_config")
    assert mc["style"] == "success" and mc["customized"] is True

    bad = await admin_client.put(
        "/api/admin/buttons/menu_config", json={"is_visible": True, "style": "purple"}
    )
    assert bad.status_code == 422  # only primary/success/danger allowed

    r = await admin_client.put(
        "/api/admin/buttons/menu_config", json={"is_visible": True, "style": None}
    )
    assert next(i for i in r.json() if i["key"] == "menu_config")["style"] is None  # cleared


# --- texts editor ------------------------------------------------------------------------------
async def test_texts_list_update_preview(admin_client: httpx.AsyncClient) -> None:
    # GET unions DB rows with the seeded defaults, so keys show even on a fresh (unseeded) schema.
    r = await admin_client.get("/api/admin/texts/")
    assert r.status_code == 200
    assert "welcome" in {t["key"] for t in r.json()}

    r = await admin_client.put("/api/admin/texts/welcome", json={"en": "Hi {name}"})
    assert r.status_code == 200
    assert r.json()["en"] == "Hi {name}"
    assert "name" in r.json()["placeholders"]

    r = await admin_client.post(
        "/api/admin/texts/preview", json={"body": "Hi {name}, {x}", "sample": {"name": "Ann"}}
    )
    body = r.json()
    assert body["rendered"] == "Hi Ann, {x}"  # provided token rendered, unknown left intact
    assert body["missing_placeholders"] == ["x"]


async def test_texts_link_preview_roundtrips(admin_client: httpx.AsyncClient) -> None:
    r = await admin_client.put(
        "/api/admin/texts/required_apps",
        json={"fa": "x", "en": "y", "ru": "z", "link_preview": False},
    )
    assert r.status_code == 200 and r.json()["link_preview"] is False
    listed = next(
        t
        for t in (await admin_client.get("/api/admin/texts/")).json()
        if t["key"] == "required_apps"
    )
    assert listed["link_preview"] is False  # the per-text flag persists + lists


# --- users + broadcast -------------------------------------------------------------------------
async def _seed_users(db_sessions) -> None:
    async with db_sessions() as s:
        s.add_all(
            [
                User(telegram_id=1001, status=UserStatus.available, panel_username=None),
                User(telegram_id=1002, status=UserStatus.active_config, panel_username="g_1002"),
                User(telegram_id=2003, status=UserStatus.banned, panel_username=None),
            ]
        )
        await s.commit()


async def test_users_list_filter_search(admin_client: httpx.AsyncClient, db_sessions) -> None:
    await _seed_users(db_sessions)
    r = await admin_client.get("/api/admin/users/")
    assert r.status_code == 200 and r.json()["total"] == 3 and len(r.json()["items"]) == 3

    r = await admin_client.get("/api/admin/users/", params={"status": "banned"})
    assert {u["telegram_id"] for u in r.json()["items"]} == {2003}

    r = await admin_client.get("/api/admin/users/", params={"search": "100"})
    assert {u["telegram_id"] for u in r.json()["items"]} == {1001, 1002}  # telegram_id substring

    r = await admin_client.get("/api/admin/users/", params={"search": "g_1002"})
    assert {u["telegram_id"] for u in r.json()["items"]} == {1002}  # panel_username match


async def test_users_pagination(admin_client: httpx.AsyncClient, db_sessions) -> None:
    await _seed_users(db_sessions)
    r = await admin_client.get("/api/admin/users/", params={"page": 1, "page_size": 2})
    body = r.json()
    assert body["total"] == 3 and len(body["items"]) == 2 and body["page_size"] == 2


async def test_user_card_and_actions(admin_client: httpx.AsyncClient, db_sessions) -> None:
    await _seed_users(db_sessions)
    r = await admin_client.get("/api/admin/users/1002")
    assert r.status_code == 200 and r.json()["telegram_id"] == 1002 and r.json()["configs"] == 0

    # ban a user with no panel account (no panel call needed) then unban
    assert (await admin_client.post("/api/admin/users/1001/ban")).json()["status"] == "banned"
    assert (await admin_client.post("/api/admin/users/1001/unban")).json()["status"] == "available"
    assert (await admin_client.post("/api/admin/users/1002/zero_referrals")).json()[
        "referral_count"
    ] == 0
    assert (await admin_client.post("/api/admin/users/1002/reclaim")).json()[
        "status"
    ] == "available"
    assert (await admin_client.post("/api/admin/users/999999/ban")).status_code == 404


async def test_broadcast_audience_and_enqueue(db_sessions, monkeypatch) -> None:
    monkeypatch.setenv("ADMIN_JWT_SECRET", _SECRET)
    monkeypatch.setenv("ADMIN_USERNAME", "root")
    monkeypatch.setenv("OWNERS", "777")
    get_settings.cache_clear()
    app = create_app()
    app.state.sessionmaker = db_sessions
    app.state.redis = fakeredis.aioredis.FakeRedis(decode_responses=True)
    app.state.panel = _StubPanel()

    class _FakeArq:
        def __init__(self) -> None:
            self.jobs: list = []

        async def enqueue_job(self, name: str, *args: object) -> None:
            self.jobs.append((name, args))

    app.state.arq = _FakeArq()
    token = create_access("root")
    async with httpx.AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://t",
        headers={"Authorization": f"Bearer {token}"},
    ) as c:
        assert (await c.get("/api/admin/broadcast/")).json()["recipients"] == 0
        r = await c.post("/api/admin/broadcast/", json={"text": "<b>hi</b>"})
        assert r.status_code == 200 and r.json()["queued"] is True
    # languages defaults to [] (everyone) — the worker reads an empty list as "all users"
    assert app.state.arq.jobs == [("broadcast_text", ("<b>hi</b>", 777, []))]
    get_settings.cache_clear()


async def _seed_langs(db_sessions) -> None:
    """3 fa · 2 en · 1 ru, for the language-targeted broadcast audience."""
    async with db_sessions() as s:
        s.add_all(
            [
                User(telegram_id=31, language=Language.fa),
                User(telegram_id=32, language=Language.fa),
                User(telegram_id=33, language=Language.fa),
                User(telegram_id=34, language=Language.en),
                User(telegram_id=35, language=Language.en),
                User(telegram_id=36, language=Language.ru),
            ]
        )
        await s.commit()


async def test_broadcast_audience_language_filter(
    admin_client: httpx.AsyncClient, db_sessions
) -> None:
    await _seed_langs(db_sessions)

    async def count(params: dict | None = None) -> int:
        return (await admin_client.get("/api/admin/broadcast/", params=params)).json()["recipients"]

    assert await count() == 6  # no param ⇒ everyone
    assert await count({"languages": ""}) == 6  # empty string ⇒ everyone
    assert await count({"languages": "fa"}) == 3
    assert await count({"languages": "fa,en"}) == 5
    assert await count({"languages": "ru"}) == 1
    # an unknown code is rejected, not silently treated as "everyone"
    assert (
        await admin_client.get("/api/admin/broadcast/", params={"languages": "xx"})
    ).status_code == 422


async def test_broadcast_enqueue_targets_languages(db_sessions, monkeypatch) -> None:
    monkeypatch.setenv("ADMIN_JWT_SECRET", _SECRET)
    monkeypatch.setenv("ADMIN_USERNAME", "root")
    monkeypatch.setenv("OWNERS", "777")
    get_settings.cache_clear()
    await _seed_langs(db_sessions)
    app = create_app()
    app.state.sessionmaker = db_sessions
    app.state.redis = fakeredis.aioredis.FakeRedis(decode_responses=True)
    app.state.panel = _StubPanel()

    class _FakeArq:
        def __init__(self) -> None:
            self.jobs: list = []

        async def enqueue_job(self, name: str, *args: object) -> None:
            self.jobs.append((name, args))

    app.state.arq = _FakeArq()
    token = create_access("root")
    async with httpx.AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://t",
        headers={"Authorization": f"Bearer {token}"},
    ) as c:
        r = await c.post("/api/admin/broadcast/", json={"text": "سلام", "languages": ["fa"]})
        assert r.status_code == 200 and r.json()["recipients"] == 3  # only fa users
        # an unknown code in the body is rejected before the job is enqueued
        assert (
            await c.post("/api/admin/broadcast/", json={"text": "x", "languages": ["xx"]})
        ).status_code == 422
    assert app.state.arq.jobs == [("broadcast_text", ("سلام", 777, ["fa"]))]
    get_settings.cache_clear()


# --- system monitoring --------------------------------------------------------------------------
async def test_system_health_endpoint_shape(admin_client: httpx.AsyncClient) -> None:
    body = (await admin_client.get("/api/admin/system/health")).json()
    assert body["status"] in ("ok", "degraded", "down")
    for key in ("db", "redis", "panel", "telegram", "webhook", "host"):
        assert key in body
    assert body["db"]["ok"] is True and body["redis"]["ok"] is True  # test DB + fakeredis
    assert body["panel"]["ok"] is False  # stub panel.system_stats() -> None
    assert body["webhook"]["configured"] is False  # no bot in tests
    assert body["host"]["cpu_count"] >= 1


async def test_system_history_empty(admin_client: httpx.AsyncClient) -> None:
    assert (await admin_client.get("/api/admin/system/history")).json() == []


async def test_system_history_returns_samples(db_sessions, monkeypatch) -> None:
    monkeypatch.setenv("ADMIN_JWT_SECRET", _SECRET)
    monkeypatch.setenv("ADMIN_USERNAME", "root")
    get_settings.cache_clear()
    app = create_app()
    app.state.sessionmaker = db_sessions
    app.state.redis = fakeredis.aioredis.FakeRedis(decode_responses=True)
    app.state.panel = _StubPanel()
    # newest-first in Redis: push older then newer; the route returns oldest-first
    await app.state.redis.rpush(HEALTH_HISTORY_KEY, "not-json")  # malformed sample is skipped
    await app.state.redis.lpush(HEALTH_HISTORY_KEY, json.dumps({"ts": "t1", "api_ms": 12}))
    await app.state.redis.lpush(HEALTH_HISTORY_KEY, json.dumps({"ts": "t2", "api_ms": 20}))
    token = create_access("root")
    async with httpx.AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://t",
        headers={"Authorization": f"Bearer {token}"},
    ) as c:
        rows = (await c.get("/api/admin/system/history?minutes=10")).json()
    assert [r["ts"] for r in rows] == ["t1", "t2"]  # oldest-first, malformed dropped
    assert rows[1]["api_ms"] == 20
    get_settings.cache_clear()
