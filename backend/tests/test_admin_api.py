"""Admin API integration (DB-gated): setup wizard, settings CRUD, dashboard stats.

Drives the real `/api/admin/*` routes with httpx + ASGITransport. ``app.state`` is set directly
(sessionmaker from the fresh test schema, fakeredis, a stub panel) so no lifespan / real Redis is
needed. Skipped without ``TEST_DATABASE_URL`` (the ``db_sessions`` fixture skips).
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from types import SimpleNamespace

import fakeredis.aioredis
import httpx
import pytest_asyncio
from httpx import ASGITransport

from gozar.config.settings import get_settings
from gozar.web.app import create_app
from gozar.web.auth.jwt import create_access

_SECRET = "test-admin-secret-0123456789-abcdef-ghijkl"  # ≥32 bytes for PyJWT


class _StubPanel:
    async def list_internal_squads(self) -> list[SimpleNamespace]:
        return [
            SimpleNamespace(uuid="sq-1", name="Squad One"),
            SimpleNamespace(uuid="sq-2", name="Squad Two"),
        ]


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


async def test_dashboard_stats_shape_on_empty_db(admin_client: httpx.AsyncClient) -> None:
    r = await admin_client.get("/api/admin/dashboard/stats")
    assert r.status_code == 200
    body = r.json()
    for key in ("total_users", "available", "active", "banned", "configs_today", "referrals"):
        assert body[key] == 0
    assert body["claims_series"] == []


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
