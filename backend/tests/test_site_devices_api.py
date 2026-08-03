"""Website device browser (/api/admin/site/devices/*) — search, inspect, moderate.

The site's users had no admin surface at all before this: no list, no lookup, no actions, and an
anti-abuse panel that counted shared fingerprints while naming none of them.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import fakeredis.aioredis
import httpx
import pytest_asyncio
from httpx import ASGITransport

from gozar.config.settings import get_settings
from gozar.db.models.site_claim import SiteClaim
from gozar.db.models.site_device import SiteDevice, SiteDeviceStatus
from gozar.db.models.site_reward import SiteReward
from gozar.web.app import create_app
from gozar.web.auth.jwt import create_access

_SECRET = "test-admin-secret-0123456789-abcdef-ghijkl"


class _StubPanel:
    def __init__(self) -> None:
        self.deleted: list[str] = []

    async def list_internal_squads(self) -> list[SimpleNamespace]:
        return []

    async def system_stats(self):
        return None

    async def delete_user_by_username(self, username: str) -> bool:
        self.deleted.append(username)
        return True


@pytest_asyncio.fixture
async def devices_client(db_sessions, monkeypatch) -> AsyncIterator[httpx.AsyncClient]:
    monkeypatch.setenv("ADMIN_JWT_SECRET", _SECRET)
    monkeypatch.setenv("ADMIN_USERNAME", "root")
    get_settings.cache_clear()
    app = create_app()
    app.state.sessionmaker = db_sessions
    app.state.redis = fakeredis.aioredis.FakeRedis(decode_responses=True)
    app.state.panel = _StubPanel()
    app.state.arq = None
    token = create_access("root")
    async with httpx.AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://t",
        headers={"Authorization": f"Bearer {token}"},
    ) as c:
        yield c
    get_settings.cache_clear()


async def _seed(db_sessions) -> None:
    now = datetime.now(UTC)
    async with db_sessions() as s:
        s.add_all(
            [
                SiteDevice(
                    uuid="dev-a",
                    handle="GZ-AAAA",
                    status=SiteDeviceStatus.active_config,
                    site_panel_username="s-aaa_1",
                    referral_count=3,
                    streak_count=4,
                    ip_bucket="10.0.0",
                    fingerprint_hash="fp-shared",
                    last_claim_at=now - timedelta(hours=2),
                ),
                SiteDevice(
                    uuid="dev-b",
                    handle="GZ-BBBB",
                    ip_bucket="10.0.0",
                    fingerprint_hash="fp-shared",
                    referred_by="dev-a",
                ),
                SiteDevice(
                    uuid="dev-c",
                    handle="GZ-CCCC",
                    status=SiteDeviceStatus.blocked,
                    ip_bucket="10.9.9",
                ),
            ]
        )
        await s.flush()
        s.add_all(
            [
                SiteClaim(device_uuid="dev-a", location="Germany"),
                SiteClaim(device_uuid="dev-a", location="Finland", is_change=True),
                SiteReward(device_uuid="dev-a", reward_type="pwa", amount_mb=200),
            ]
        )
        await s.commit()


async def test_requires_auth(devices_client: httpx.AsyncClient) -> None:
    r = await devices_client.get("/api/admin/site/devices/", headers={"Authorization": ""})
    assert r.status_code == 401


async def test_lists_devices_newest_first(devices_client: httpx.AsyncClient, db_sessions) -> None:
    await _seed(db_sessions)
    body = (await devices_client.get("/api/admin/site/devices/")).json()
    assert body["total"] == 3
    assert {d["handle"] for d in body["items"]} == {"GZ-AAAA", "GZ-BBBB", "GZ-CCCC"}
    # The fingerprint HASH itself identifies a browser — expose only whether one exists.
    assert all("fingerprint_hash" not in d for d in body["items"])
    assert next(d for d in body["items"] if d["uuid"] == "dev-a")["has_fingerprint"] is True


async def test_search_matches_handle_uuid_and_panel_username(
    devices_client: httpx.AsyncClient, db_sessions
) -> None:
    await _seed(db_sessions)
    for query, expected in (("GZ-AAAA", "dev-a"), ("dev-b", "dev-b"), ("s-aaa", "dev-a")):
        body = (await devices_client.get(f"/api/admin/site/devices/?search={query}")).json()
        assert [d["uuid"] for d in body["items"]] == [expected], query


async def test_filters_by_status_and_ip_bucket(
    devices_client: httpx.AsyncClient, db_sessions
) -> None:
    await _seed(db_sessions)
    blocked = (await devices_client.get("/api/admin/site/devices/?status=blocked")).json()
    assert [d["uuid"] for d in blocked["items"]] == ["dev-c"]

    # This is what the anti-abuse panel deep-links into: the actual devices behind a shared IP.
    bucket = (await devices_client.get("/api/admin/site/devices/?ip_bucket=10.0.0")).json()
    assert bucket["total"] == 2
    assert {d["uuid"] for d in bucket["items"]} == {"dev-a", "dev-b"}

    assert (await devices_client.get("/api/admin/site/devices/?status=nonsense")).status_code == 422


async def test_device_card_gathers_the_detail_view(
    devices_client: httpx.AsyncClient, db_sessions
) -> None:
    await _seed(db_sessions)
    body = (await devices_client.get("/api/admin/site/devices/dev-a")).json()
    assert body["claims"] == 2
    assert {c["location"] for c in body["recent_claims"]} == {"Germany", "Finland"}
    assert body["rewards"] == ["pwa"]
    assert body["invited"] == 1  # dev-b arrived through dev-a
    assert body["streak_count"] == 4
    assert (await devices_client.get("/api/admin/site/devices/nope")).status_code == 404


async def test_fingerprint_peers_names_the_shared_devices(
    devices_client: httpx.AsyncClient, db_sessions
) -> None:
    await _seed(db_sessions)
    peers = (await devices_client.get("/api/admin/site/devices/dev-a/peers")).json()
    assert [p["uuid"] for p in peers] == ["dev-b"]
    # A device with no fingerprint has no peers rather than matching every other null.
    assert (await devices_client.get("/api/admin/site/devices/dev-c/peers")).json() == []


async def test_block_revokes_the_panel_account_and_flips_status(
    devices_client: httpx.AsyncClient, db_sessions
) -> None:
    await _seed(db_sessions)
    body = (await devices_client.post("/api/admin/site/devices/dev-a/block")).json()
    assert body["status"] == "blocked"
    # The live trial is revoked too — blocking must not leave working access behind.
    assert body["site_panel_username"] is None

    async with db_sessions() as s:
        row = await s.get(SiteDevice, "dev-a")
        assert row is not None and row.status == SiteDeviceStatus.blocked


async def test_unblock_restores_the_device(devices_client: httpx.AsyncClient, db_sessions) -> None:
    await _seed(db_sessions)
    await devices_client.post("/api/admin/site/devices/dev-a/block")
    body = (await devices_client.post("/api/admin/site/devices/dev-a/unblock")).json()
    assert body["status"] == "available"


async def test_reset_clears_the_cooldown_but_keeps_the_history(
    devices_client: httpx.AsyncClient, db_sessions
) -> None:
    await _seed(db_sessions)
    body = (await devices_client.post("/api/admin/site/devices/dev-a/reset")).json()
    assert body["status"] == "available"
    # last_claim_at is the rolling-cooldown anchor; clearing it is what lets them claim again.
    assert body["last_claim_at"] is None

    # Forgiveness, not a wipe: the row and its claim history survive.
    card = (await devices_client.get("/api/admin/site/devices/dev-a")).json()
    assert card["claims"] == 2


async def test_actions_404_on_an_unknown_device(devices_client: httpx.AsyncClient) -> None:
    for action in ("block", "unblock", "reset"):
        r = await devices_client.post(f"/api/admin/site/devices/nope/{action}")
        assert r.status_code == 404
