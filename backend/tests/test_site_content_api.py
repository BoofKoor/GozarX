"""Website copy editor (/api/admin/site/content) + the public overrides it feeds.

Only four site strings used to be editable; everything else a visitor reads was a compile-time
constant in the site's design copy. These tests pin the contract that makes the wider set editable:
a blank row means "use the site's own copy", and the public endpoint only reports real overrides.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from types import SimpleNamespace

import fakeredis.aioredis
import httpx
import pytest_asyncio
from httpx import ASGITransport

from gozar.config.settings import get_settings
from gozar.services.site_copy_keys import SITE_COPY_DEFAULTS, SITE_COPY_KEYS, content_key
from gozar.web.app import create_app
from gozar.web.auth.jwt import create_access

_SECRET = "test-admin-secret-0123456789-abcdef-ghijkl"


class _StubPanel:
    async def list_internal_squads(self) -> list[SimpleNamespace]:
        return []

    async def system_stats(self):
        return None


@pytest_asyncio.fixture
async def client(db_sessions, monkeypatch) -> AsyncIterator[httpx.AsyncClient]:
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


async def test_requires_auth(client: httpx.AsyncClient) -> None:
    r = await client.get("/api/admin/site/content/", headers={"Authorization": ""})
    assert r.status_code == 401


async def test_lists_every_editable_key_with_its_default(client: httpx.AsyncClient) -> None:
    items = (await client.get("/api/admin/site/content/")).json()
    by_key = {i["key"]: i for i in items}

    # Every allowlisted design-copy key is offered, carrying the site's in-code copy as the default
    # so the operator can see what a string currently says before changing it.
    for design in SITE_COPY_KEYS:
        item = by_key[content_key(design)]
        assert item["fa"] == "" and item["overridden"] is False
        assert item["default_fa"] == SITE_COPY_DEFAULTS[design]["fa"]

    # The original four keys stay under their existing names.
    assert "site_hero_title" in by_key and "site_meta_description" in by_key
    assert by_key["site_hero_title"]["group"] == "hero"


async def test_saving_an_override_marks_it_and_reaches_the_public_endpoint(
    client: httpx.AsyncClient,
) -> None:
    key = content_key("hero_eyebrow")
    r = await client.put(f"/api/admin/site/content/{key}", json={"fa": "تست", "en": "test"})
    assert r.status_code == 200
    assert r.json()["overridden"] is True

    public = (await client.get("/api/public/site-copy?locale=fa")).json()
    assert public["overrides"]["hero_eyebrow"] == "تست"
    # Only customised keys appear — the site falls back to its own copy for everything else.
    assert "hero_h1_a" not in public["overrides"]

    en = (await client.get("/api/public/site-copy?locale=en")).json()
    assert en["overrides"]["hero_eyebrow"] == "test"


async def test_clearing_a_value_restores_the_site_default(client: httpx.AsyncClient) -> None:
    key = content_key("w_title")
    await client.put(f"/api/admin/site/content/{key}", json={"fa": "چیزی", "en": "something"})
    assert (await client.get("/api/public/site-copy?locale=fa")).json()["overrides"]["w_title"]

    r = await client.put(f"/api/admin/site/content/{key}", json={"fa": "", "en": ""})
    assert r.json()["overridden"] is False
    # A blank row must NOT blank the heading on the live site — it means "use the in-code copy".
    public = (await client.get("/api/public/site-copy?locale=fa")).json()
    assert "w_title" not in public["overrides"]


async def test_whitespace_only_is_treated_as_cleared(client: httpx.AsyncClient) -> None:
    key = content_key("cta_get")
    await client.put(f"/api/admin/site/content/{key}", json={"fa": "   "})
    public = (await client.get("/api/public/site-copy?locale=fa")).json()
    assert "cta_get" not in public["overrides"]


async def test_rejects_a_key_outside_the_allowlist(client: httpx.AsyncClient) -> None:
    # This endpoint writes into the SHARED content table — it must never become a way to create
    # arbitrary rows (e.g. overwrite a bot message).
    for bad in ("start_message", "site_copy_not_a_key", "anything"):
        r = await client.put(f"/api/admin/site/content/{bad}", json={"fa": "x"})
        assert r.status_code == 404, bad


async def test_public_site_copy_still_answers_on_a_fresh_install(client: httpx.AsyncClient) -> None:
    body = (await client.get("/api/public/site-copy?locale=fa")).json()
    # Nothing edited: the four legacy fields fall back to their seeded values (or null) and the
    # overrides map is empty, so the site renders exactly as it did before this existed.
    assert body["overrides"] == {}
    assert "hero_title" in body and "meta_title" in body
    assert (await client.get("/api/public/site-copy?locale=ru")).status_code == 422
