"""Admin API integration (DB-gated): setup wizard, settings CRUD, dashboard stats.

Drives the real `/api/admin/*` routes with httpx + ASGITransport. ``app.state`` is set directly
(sessionmaker from the fresh test schema, fakeredis, a stub panel) so no lifespan / real Redis is
needed. Skipped without ``TEST_DATABASE_URL`` (the ``db_sessions`` fixture skips).
"""

from __future__ import annotations

import csv
import io
import json
from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import fakeredis.aioredis
import httpx
import pytest_asyncio
from httpx import ASGITransport

from gozar.cache.redis import HEALTH_HISTORY_KEY
from gozar.config.reporting import DISPLAY_TZ
from gozar.config.settings import get_settings
from gozar.db.models.config_log import ConfigLog
from gozar.db.models.enums import Language, UserStatus
from gozar.db.models.usage_sample import UsageSample
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

    async def squad_location_names(self, squad: str) -> list[str]:
        return ["Germany", "Finland"]

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
        json={
            "trial_squad": "sq-1",
            "locations": ["Germany", "Finland"],
            "daily_limit_mb": 2048,
        },
    )
    assert r.status_code == 200 and r.json()["completed"] is True
    assert (await admin_client.get("/api/admin/setup/status")).json()["completed"] is True
    settings = (await admin_client.get("/api/admin/settings/")).json()
    assert settings["trial_squad"] == "sq-1"
    assert settings["locations"] == ["Germany", "Finland"]
    assert settings["daily_limit_mb"] == 2048


async def test_setup_rejects_a_location_the_chosen_squad_does_not_serve(
    admin_client: httpx.AsyncClient,
) -> None:
    """The wizard used to store whatever it was handed, straight past the settings check."""
    r = await admin_client.post(
        "/api/admin/setup/", json={"trial_squad": "sq-1", "locations": ["Germany", "Narnia"]}
    )
    assert r.status_code == 400
    assert "Narnia" in r.json()["detail"]
    # Nothing persisted — the wizard is still open.
    assert (await admin_client.get("/api/admin/setup/status")).json()["completed"] is False


async def test_settings_put_partial_update(admin_client: httpx.AsyncClient) -> None:
    r = await admin_client.put(
        "/api/admin/settings/", json={"ads_enabled": True, "trial_hours": 48}
    )
    assert r.status_code == 200
    body = r.json()
    assert body["ads_enabled"] is True
    assert body["trial_hours"] == 48


async def test_settings_put_floors_negative_numerics(admin_client: httpx.AsyncClient) -> None:
    # A negative daily_limit_mb makes compute_traffic_bytes go negative → every claim PanelError.
    # trial_hours floors to 1; the rest to 0 (mirrors the site settings endpoint).
    r = await admin_client.put(
        "/api/admin/settings/",
        json={"daily_limit_mb": -1024, "referral_reward_mb": -5, "trial_hours": 0},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["daily_limit_mb"] == 0
    assert body["referral_reward_mb"] == 0
    assert body["trial_hours"] == 1


async def test_settings_rejects_a_location_the_bot_squad_does_not_serve(
    admin_client: httpx.AsyncClient,
) -> None:
    """The website settings and wizard already refused these; the BOT's own list did not.

    A name the squad doesn't serve is offered in the bot's location picker and then matches no
    remark, so the user picks it and the claim dead-ends.
    """
    await admin_client.post("/api/admin/setup/", json={"trial_squad": "sq-1", "locations": []})
    r = await admin_client.put("/api/admin/settings/", json={"locations": ["Germany", "Narnia"]})
    assert r.status_code == 400
    detail = r.json()["detail"]
    assert "Narnia" in detail and "Finland" in detail  # names the bad value AND the real options
    assert (await admin_client.get("/api/admin/settings/")).json()["locations"] == []


async def test_settings_accepts_a_served_location(admin_client: httpx.AsyncClient) -> None:
    await admin_client.post("/api/admin/setup/", json={"trial_squad": "sq-1", "locations": []})
    r = await admin_client.put("/api/admin/settings/", json={"locations": ["Finland"]})
    assert r.status_code == 200
    assert r.json()["locations"] == ["Finland"]


async def test_settings_stores_locations_when_no_squad_is_configured(
    admin_client: httpx.AsyncClient,
) -> None:
    """Unverifiable is not invalid — with no squad set there is nothing to check against, and the
    admin must not be blocked out of their own settings."""
    r = await admin_client.put("/api/admin/settings/", json={"locations": ["Anywhere"]})
    assert r.status_code == 200
    assert r.json()["locations"] == ["Anywhere"]


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
    # Daily series are zero-filled to exactly range_days ascending points (no collapsed time axis),
    # so an empty DB yields 14 all-zero days rather than [].
    for key in ("claims_series", "signups_series"):
        series = body[key]
        assert len(series) == 14
        assert all(pt["count"] == 0 for pt in series)
        assert [pt["day"] for pt in series] == sorted(pt["day"] for pt in series)
    # richer payload defaults: online -> active fallback (0), panel unreachable, default range
    assert body["online_now"] == 0
    assert body["range_days"] == 14
    assert body["panel_online"] is False
    for key in ("new_today", "new_this_week", "conversion_pct", "avg_referrals", "nodes_online"):
        assert body[key] == 0
    assert body["panel_status_counts"] == {}
    for key in ("languages", "top_locations", "top_referrers"):
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


async def test_dashboard_analytics_empty(admin_client: httpx.AsyncClient) -> None:
    body = (await admin_client.get("/api/admin/dashboard/analytics")).json()
    for key in ("dau", "wau", "mau", "claimers_all_time", "first_claimers_in_range"):
        assert body[key] == 0
    assert body["stickiness_pct"] == 0.0
    # An empty cohort has no median at all — absent, not zero — and no baseline to compare to.
    assert body["median_hours_to_claim"] == {"value": None, "previous": None, "change_pct": None}
    assert body["heatmap"] == [] and body["claims_distribution"] == {}
    assert body["referral"]["k_factor"] == 0.0


async def test_activation_metrics_follow_the_range_control(
    admin_client: httpx.AsyncClient, db_sessions
) -> None:
    """The range control has to MOVE these two figures, not sit above frozen all-time numbers.

    Two cohorts: one that activated inside a 7-day window and one that activated in the 7 days
    before it, each with a different signup→first-claim gap. A 7-day request must see only the
    recent cohort as `value` and only the older one as `previous`.
    """
    now = datetime.now(UTC)
    async with db_sessions() as s:
        s.add_all(
            [
                # Recent cohort: signed up 2 days ago, first claim 1 hour later → fast.
                User(telegram_id=21, language=Language.fa, created_at=now - timedelta(days=2)),
                # Older cohort: signed up 12 days ago, first claim 48 hours later → slow.
                User(telegram_id=22, language=Language.fa, created_at=now - timedelta(days=12)),
            ]
        )
        await s.flush()
        s.add_all(
            [
                ConfigLog(
                    user_id=21,
                    location="DE",
                    created_at=now - timedelta(days=2) + timedelta(hours=1),
                ),
                ConfigLog(
                    user_id=22,
                    location="DE",
                    created_at=now - timedelta(days=10),
                ),
            ]
        )
        await s.commit()

    body = (await admin_client.get("/api/admin/dashboard/analytics?days=7")).json()
    assert body["first_claimers_in_range"] == 1  # only the recent activation
    assert body["median_hours_to_claim"]["value"] == 1.0
    assert body["median_hours_to_claim"]["previous"] == 48.0
    # Faster is better here, so the sign is negative and the label carries the meaning.
    assert body["median_hours_to_claim"]["change_pct"] is not None
    assert body["median_hours_to_claim"]["change_pct"] < 0
    # 24h activation: the recent cohort made it, the older one did not.
    assert body["activation_24h"]["value"] == 100.0
    assert body["activation_24h"]["previous"] == 0.0
    # Both users have ever claimed, whatever window is asked for.
    assert body["claimers_all_time"] == 2

    # Widen the window and the two cohorts merge into one, which is the point of the control.
    wide = (await admin_client.get("/api/admin/dashboard/analytics?days=30")).json()
    assert wide["first_claimers_in_range"] == 2
    assert wide["activation_24h"]["value"] == 50.0


async def test_dashboard_analytics_aggregations(
    admin_client: httpx.AsyncClient, db_sessions
) -> None:
    async with db_sessions() as s:
        s.add_all(
            [
                User(telegram_id=11, language=Language.fa, referral_count=1),
                User(telegram_id=12, language=Language.fa),
                User(telegram_id=13, language=Language.en, referred_by=11),  # invited, claims
            ]
        )
        await s.flush()
        s.add_all(
            [
                ConfigLog(user_id=11, location="DE"),
                ConfigLog(user_id=11, location="DE"),  # power user (2 claims)
                ConfigLog(user_id=13, location="NL"),  # invited user activates
            ]
        )
        await s.commit()

    body = (await admin_client.get("/api/admin/dashboard/analytics")).json()
    assert body["dau"] == 2 and body["wau"] == 2 and body["mau"] == 2  # users 11 & 13 claimed today
    assert body["stickiness_pct"] == 100.0
    assert body["claimers_all_time"] == 2
    assert body["first_claimers_in_range"] == 2  # both activated inside the window
    assert body["activation_24h"]["value"] == 100.0  # both first-claimed within 24h of signup
    # Nothing happened in the window before this one, so there is no comparison to draw.
    assert body["activation_24h"]["previous"] == 0.0
    assert body["activation_24h"]["change_pct"] is None
    assert body["claims_distribution"] == {"1": 1, "2-3": 1}  # u13 once, u11 twice
    assert body["referral"] == {
        "joined": 1,
        "joined_claimed": 1,
        "invitee_conversion_pct": 100.0,
        "k_factor": round(1 / 3, 2),
        # The share's denominator is everyone who signed up at or after the first referral — here
        # all three, since they are seeded together. On a live install it excludes the legacy
        # imported rows, for which `referred_by` is structurally null.
        "eligible": 3,
        "joined_share_pct": 33.3,
    }
    assert sum(cell["count"] for cell in body["heatmap"]) == 3
    fa = next(r for r in body["reminder_by_language"] if r["label"] == "fa")
    assert fa["on"] == 2  # users 11 & 12 default reminders on


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

        async def enqueue_job(self, name: str, *args: object, **kw: object) -> None:
            # `**kw` catches arq's `_defer_until`, which a scheduled send passes. Without it a
            # stub that is merely out of date reads as the route being broken.
            self.jobs.append((name, args))

    app.state.arq = _FakeArq()
    token = create_access("root")
    async with httpx.AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://t",
        headers={"Authorization": f"Bearer {token}"},
    ) as c:
        # A send to nobody is refused rather than queued: it would otherwise land in the history
        # as a "successful" broadcast that reached zero people.
        assert (await c.get("/api/admin/broadcast/")).json()["recipients"] == 0
        assert (await c.post("/api/admin/broadcast/", json={"text": "x"})).status_code == 422

        async with db_sessions() as s:
            s.add(User(telegram_id=99, language=Language.fa))
            await s.commit()
        assert (await c.get("/api/admin/broadcast/")).json()["recipients"] == 1
        r = await c.post("/api/admin/broadcast/", json={"text": "<b>hi</b>"})
        assert r.status_code == 200 and r.json()["queued"] is True
    # languages defaults to [] (everyone) — the worker reads an empty list as "all users"
    name, args = app.state.arq.jobs[0]
    assert name == "broadcast_text"
    assert args[:3] == ("<b>hi</b>", 777, [])
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


async def test_broadcast_drafts_round_trip(admin_client: httpx.AsyncClient) -> None:
    """Save, overwrite, list, delete — the whole reason a draft is server-side rather than in the
    browser is that it has to survive being closed, so the round trip is the feature."""
    saved = (
        await admin_client.post(
            "/api/admin/broadcast/drafts",
            json={
                "text": "خط اول\nخط دوم",
                "languages": ["fa"],
                "only_referrers": True,
                "buttons": [{"text": "کانال", "url": "https://t.me/x"}],
                "send_hour": 21,
            },
        )
    ).json()
    # The title comes from the FIRST line, so a draft never has to be named to be kept.
    assert saved["title"] == "خط اول"
    assert saved["languages"] == "fa"
    assert saved["send_hour"] == 21
    assert saved["buttons"] == [{"text": "کانال", "url": "https://t.me/x"}]

    # Saving again with the same id OVERWRITES rather than minting a second near-identical copy.
    again = (
        await admin_client.post(
            "/api/admin/broadcast/drafts", json={"id": saved["id"], "text": "بازنویسی"}
        )
    ).json()
    assert again["id"] == saved["id"]
    assert again["title"] == "بازنویسی"
    assert (await admin_client.get("/api/admin/broadcast/drafts")).json() == [again]

    # A button URL Telegram would reject is refused here too — a draft restored months later
    # should not be the first time anyone finds out.
    bad = await admin_client.post(
        "/api/admin/broadcast/drafts",
        json={"text": "x", "buttons": [{"text": "y", "url": "http://insecure"}]},
    )
    assert bad.status_code == 422

    assert (
        await admin_client.delete(f"/api/admin/broadcast/drafts/{saved['id']}")
    ).status_code == 204
    assert (await admin_client.get("/api/admin/broadcast/drafts")).json() == []
    # Deleting it twice is a 404, not a silent success.
    assert (
        await admin_client.delete(f"/api/admin/broadcast/drafts/{saved['id']}")
    ).status_code == 404


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

        async def enqueue_job(self, name: str, *args: object, **kw: object) -> None:
            # `**kw` catches arq's `_defer_until`, which a scheduled send passes. Without it a
            # stub that is merely out of date reads as the route being broken.
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
    # Positional prefix only: the job also carries the two audience refinements, the buttons and
    # the log id, and pinning the whole tuple makes every future argument a test failure rather
    # than a behaviour change.
    name, args = app.state.arq.jobs[0]
    assert name == "broadcast_text"
    assert args[:3] == ("سلام", 777, ["fa"])
    get_settings.cache_clear()


async def test_dashboard_usage_reports_its_own_warmup(admin_client: httpx.AsyncClient) -> None:
    """With nothing recorded, the route must say so rather than report zero traffic.

    "We carried no bytes" and "we were not recording yet" are different facts, and the panel picks
    its empty state from `recording_since` — so a route that returned 0 samples with a timestamp,
    or a timestamp with no samples, would put the wrong sentence on the screen.
    """
    body = (await admin_client.get("/api/admin/dashboard/usage")).json()
    assert body["recording_since"] is None
    assert body["samples"] == 0
    assert body["daily"] == []
    assert body["traffic"]["value"] == 0


async def test_dashboard_usage_windows_and_flags_a_reset(
    admin_client: httpx.AsyncClient, db_sessions
) -> None:
    """The window figures difference the cumulative counter, and a counter that went backwards is
    flagged rather than reported as negative traffic."""
    gb = 1024**3
    local_today = datetime.now(DISPLAY_TZ).replace(hour=0, minute=0, second=0, microsecond=0)

    def at(days_ago: int, hour: int) -> datetime:
        return (local_today - timedelta(days=days_ago, hours=-hour)).astimezone(UTC)

    async with db_sessions() as s:
        s.add_all(
            [
                UsageSample(captured_at=at(3, 2), total_bytes=500 * gb, online_now=40),
                UsageSample(captured_at=at(2, 2), total_bytes=560 * gb, online_now=95),
                # The counter drops: a panel restart, or a manual traffic reset.
                UsageSample(captured_at=at(1, 2), total_bytes=10 * gb, online_now=70),
            ]
        )
        await s.commit()

    body = (await admin_client.get("/api/admin/dashboard/usage", params={"days": 7})).json()
    assert body["samples"] == 3
    assert body["recording_since"] is not None
    assert body["peak_online"]["value"] == 95

    days = {d["day"]: d for d in body["daily"]}
    reset_days = [d for d in body["daily"] if d["counter_reset"]]
    assert len(reset_days) == 1
    # The reset day reports zero rather than a negative half-terabyte.
    assert reset_days[0]["bytes"] == 0
    # The ordinary day before it still carries its real 60 GB.
    ordinary = [d for d in body["daily"] if not d["counter_reset"]]
    assert any(d["bytes"] == 60 * gb for d in ordinary), days


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


async def test_dashboard_supports_a_90_day_window(admin_client: httpx.AsyncClient) -> None:
    body = (await admin_client.get("/api/admin/dashboard/stats?days=90")).json()
    assert body["range_days"] == 90
    assert len(body["claims_series"]) == 90  # zero-filled to exactly the window length


async def test_dashboard_period_comparison_is_same_length_and_adjacent(
    admin_client: httpx.AsyncClient, db_sessions
) -> None:
    now = datetime.now(UTC)
    async with db_sessions() as s:
        s.add_all(
            [
                User(telegram_id=21, created_at=now - timedelta(days=2)),  # inside a 7-day window
                User(telegram_id=22, created_at=now - timedelta(days=9)),  # inside the PREVIOUS one
            ]
        )
        await s.flush()
        s.add_all(
            [
                ConfigLog(user_id=21, location="DE", created_at=now - timedelta(days=2)),
                ConfigLog(user_id=22, location="NL", created_at=now - timedelta(days=9)),
                ConfigLog(user_id=22, location="NL", created_at=now - timedelta(days=10)),
            ]
        )
        await s.commit()

    body = (await admin_client.get("/api/admin/dashboard/stats?days=7")).json()
    assert body["signups_in_range"] == 1 and body["signups_prev_range"] == 1
    assert body["signups_delta_pct"] == 0.0
    assert body["claims_in_range"] == 1 and body["claims_prev_range"] == 2
    assert body["claims_delta_pct"] == -50.0
    assert body["claimers_in_range"] == 1 and body["claimers_prev_range"] == 1


async def test_dashboard_delta_is_null_without_a_baseline(
    admin_client: httpx.AsyncClient, db_sessions
) -> None:
    async with db_sessions() as s:
        s.add(User(telegram_id=31))
        await s.commit()
    body = (await admin_client.get("/api/admin/dashboard/stats?days=7")).json()
    # A launch window with real signups must not read as "0% — flat" just because there is nothing
    # to compare against; the frontend renders null as a "new" badge instead.
    assert body["signups_in_range"] == 1
    assert body["signups_prev_range"] == 0
    assert body["signups_delta_pct"] is None


async def test_dashboard_analytics_new_vs_returning_and_active_series(
    admin_client: httpx.AsyncClient, db_sessions
) -> None:
    now = datetime.now(UTC)
    async with db_sessions() as s:
        s.add_all([User(telegram_id=41), User(telegram_id=42)])
        await s.flush()
        s.add_all(
            [
                # u41 claimed days ago and again today -> today it is RETURNING.
                ConfigLog(user_id=41, location="DE", created_at=now - timedelta(days=3)),
                ConfigLog(user_id=41, location="DE", created_at=now),
                # u42's only claim is today -> NEW.
                ConfigLog(user_id=42, location="NL", created_at=now),
            ]
        )
        await s.commit()

    body = (await admin_client.get("/api/admin/dashboard/analytics?days=7")).json()
    assert len(body["active_users_series"]) == 7  # zero-filled to the window
    assert len(body["new_vs_returning"]) == 7
    today = now.date().isoformat()
    row = next(r for r in body["new_vs_returning"] if r["day"] == today)
    assert row["new"] == 1 and row["returning"] == 1
    assert sum(c["count"] for c in body["signup_heatmap"]) == 2


async def test_dashboard_analytics_reports_the_configured_referral_cap(
    admin_client: httpx.AsyncClient, db_sessions
) -> None:
    async with db_sessions() as s:
        s.add_all(
            [
                User(telegram_id=51, referral_count=10),
                User(telegram_id=52, referral_count=2),
                User(telegram_id=53, referral_count=0),
            ]
        )
        await s.commit()
    # The cap comes from settings — never a hardcoded number.
    await admin_client.put("/api/admin/settings/", json={"referral_reward_limit": 10})

    cap = (await admin_client.get("/api/admin/dashboard/analytics")).json()["referral_cap"]
    assert cap == {"limit": 10, "at_cap": 1, "with_referrals": 2}


async def test_dashboard_retention_cohorts(admin_client: httpx.AsyncClient, db_sessions) -> None:
    now = datetime.now(UTC)
    async with db_sessions() as s:
        s.add_all(
            [
                User(telegram_id=61, created_at=now - timedelta(weeks=2)),
                User(telegram_id=62, created_at=now - timedelta(weeks=2)),
            ]
        )
        await s.flush()
        s.add_all(
            [
                # both activate in their signup week; only u61 comes back later
                ConfigLog(user_id=61, location="DE", created_at=now - timedelta(weeks=2)),
                ConfigLog(user_id=62, location="DE", created_at=now - timedelta(weeks=2)),
                ConfigLog(user_id=61, location="DE", created_at=now - timedelta(days=2)),
            ]
        )
        await s.commit()

    body = (await admin_client.get("/api/admin/dashboard/retention?weeks=4")).json()
    assert body["weeks"] == 4
    cohort = next(c for c in body["cohorts"] if c["size"] == 2)
    assert cohort["retention"][0] == 100.0  # both claimed in their signup week
    assert cohort["retention"][-1] == 50.0  # one of two returned in the latest week


async def test_cohort_row_is_as_long_as_the_weeks_that_elapsed(
    admin_client: httpx.AsyncClient, db_sessions
) -> None:
    """A cohort nobody returned to must report 0%, not a short row.

    Sized from the data — `max(offset) + 1` — a cohort where nobody came back after week one got a
    one-column row, which is exactly what a cohort two days old looks like. The dashboard drops
    short rows because their second week has not happened, so a genuine 0% was silently excluded
    from the retention average instead of dragging it down as it should.
    """
    now = datetime.now(UTC)
    async with db_sessions() as s:
        s.add_all(
            [
                # Three weeks old, claimed once on day one and never again.
                User(telegram_id=71, created_at=now - timedelta(weeks=3)),
                # Two days old — its second week genuinely has not arrived.
                User(telegram_id=72, created_at=now - timedelta(days=2)),
            ]
        )
        await s.flush()
        s.add_all(
            [
                ConfigLog(user_id=71, location="DE", created_at=now - timedelta(weeks=3)),
                ConfigLog(user_id=72, location="DE", created_at=now - timedelta(days=2)),
            ]
        )
        await s.commit()

    body = (await admin_client.get("/api/admin/dashboard/retention?weeks=8")).json()
    rows = {c["week"]: c["retention"] for c in body["cohorts"]}
    old = next(r for w, r in rows.items() if len(r) >= 4)
    # Four elapsed weeks, so four columns — and the three after signup are real zeros.
    assert old[0] == 100.0
    assert old[1:4] == [0.0, 0.0, 0.0]
    # The young cohort still reports one column, so the dashboard keeps excluding it.
    young = min(rows.values(), key=len)
    assert len(young) == 1


async def test_dashboard_retention_weeks_is_bounded(admin_client: httpx.AsyncClient) -> None:
    assert (await admin_client.get("/api/admin/dashboard/retention?weeks=1")).status_code == 422
    assert (await admin_client.get("/api/admin/dashboard/retention?weeks=99")).status_code == 422


async def test_dashboard_csv_export(admin_client: httpx.AsyncClient, db_sessions) -> None:
    async with db_sessions() as s:
        s.add(User(telegram_id=71))
        await s.flush()
        s.add(ConfigLog(user_id=71, location="DE"))
        await s.commit()

    r = await admin_client.get("/api/admin/dashboard/export.csv?days=7")
    assert r.status_code == 200
    assert "text/csv" in r.headers["content-type"]
    assert "attachment" in r.headers["content-disposition"]
    rows = list(csv.reader(io.StringIO(r.text)))
    assert rows[0] == [
        "day",
        "signups",
        "claims",
        "active_users",
        "new_claimers",
        "returning_claimers",
    ]
    assert len(rows) == 8  # header + 7 zero-filled days
    today = datetime.now(UTC).date().isoformat()
    assert [r for r in rows[1:] if r[0] == today][0][1:] == ["1", "1", "1", "1", "0"]
