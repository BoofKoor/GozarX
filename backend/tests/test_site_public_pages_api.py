"""Public SEO-landing endpoints (``/api/public/pages``) — integration, DB-gated.

Mirrors ``test_site_admin_api.py``'s app wiring (fresh test schema, fakeredis, stub panel) but the
client carries NO Authorization header: these routes are open by design. Skipped without
``TEST_DATABASE_URL``.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from types import SimpleNamespace

import fakeredis.aioredis
import httpx
import pytest_asyncio
from httpx import ASGITransport

from gozar.db.models.site_landing_page import SiteLandingPage
from gozar.web.app import create_app


class _StubPanel:
    async def list_internal_squads(self) -> list[SimpleNamespace]:
        return []

    async def system_stats(self):
        return None


def _build_app(db_sessions):
    app = create_app()
    app.state.sessionmaker = db_sessions
    app.state.redis = fakeredis.aioredis.FakeRedis(decode_responses=True)
    app.state.panel = _StubPanel()
    app.state.arq = None
    return app


def _row(slug: str, locale: str = "fa", *, published: bool = True, **kw) -> SiteLandingPage:
    return SiteLandingPage(
        slug=slug,
        locale=locale,
        title=kw.get("title", f"{slug} title"),
        meta_description=kw.get("meta_description", f"{slug} desc"),
        heading=kw.get("heading"),
        body=kw.get("body", f"<p>{slug} body</p>"),
        location_remark=kw.get("location_remark"),
        published=published,
    )


@pytest_asyncio.fixture
async def public_client(db_sessions) -> AsyncIterator[httpx.AsyncClient]:
    async with db_sessions() as s:
        s.add_all(
            [
                _row("free-v2ray-config", "fa", heading="H1", location_remark="آلمان"),
                _row("free-v2ray-config", "en", title="en title", body="<p>en body</p>"),
                _row("fa-only", "fa"),
                _row("hidden", "fa", published=False),
                _row("en-hidden", "fa", title="fa fallback title"),
                _row("en-hidden", "en", published=False),
            ]
        )
        await s.commit()
    app = _build_app(db_sessions)
    async with httpx.AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
        yield c


async def test_list_returns_only_published(public_client: httpx.AsyncClient) -> None:
    r = await public_client.get("/api/public/pages")
    assert r.status_code == 200
    slugs = [(p["slug"], p["locale"]) for p in r.json()]
    assert ("hidden", "fa") not in slugs
    assert ("en-hidden", "en") not in slugs
    assert ("free-v2ray-config", "fa") in slugs
    # summaries stay light: no body field in the list payload
    assert "body" not in r.json()[0]


async def test_list_locale_filter_and_validation(public_client: httpx.AsyncClient) -> None:
    r = await public_client.get("/api/public/pages?locale=en")
    assert r.status_code == 200
    assert {p["locale"] for p in r.json()} == {"en"}
    assert (await public_client.get("/api/public/pages?locale=ru")).status_code == 422


async def test_get_page_fa(public_client: httpx.AsyncClient) -> None:
    r = await public_client.get("/api/public/pages/free-v2ray-config")
    assert r.status_code == 200
    data = r.json()
    assert data["locale"] == "fa"
    assert data["heading"] == "H1"
    assert data["body"].startswith("<p>")
    assert data["location_remark"] == "آلمان"


async def test_get_page_en_row_wins_for_en(public_client: httpx.AsyncClient) -> None:
    r = await public_client.get("/api/public/pages/free-v2ray-config?locale=en")
    assert r.status_code == 200
    assert r.json()["locale"] == "en"
    assert r.json()["title"] == "en title"


async def test_get_page_en_falls_back_to_fa(public_client: httpx.AsyncClient) -> None:
    # no en row at all -> fa served, and the response says so
    r = await public_client.get("/api/public/pages/fa-only?locale=en")
    assert r.status_code == 200
    assert r.json()["locale"] == "fa"
    # en row exists but is UNPUBLISHED -> fallback must skip it and serve the published fa row
    r = await public_client.get("/api/public/pages/en-hidden?locale=en")
    assert r.status_code == 200
    assert r.json()["locale"] == "fa"
    assert r.json()["title"] == "fa fallback title"


async def test_get_page_404s(public_client: httpx.AsyncClient) -> None:
    assert (await public_client.get("/api/public/pages/nope")).status_code == 404
    # unpublished row is invisible publicly
    assert (await public_client.get("/api/public/pages/hidden")).status_code == 404
    # invalid locale rejected
    assert (
        await public_client.get("/api/public/pages/free-v2ray-config?locale=ru")
    ).status_code == 422
