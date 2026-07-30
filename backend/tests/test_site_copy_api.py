"""Public site-copy endpoint (``/api/public/site-copy``) — editable hero + homepage-meta strings.

DB-gated (skipped without ``TEST_DATABASE_URL``). Proves the site reads the ``content`` rows the
admin Texts panel edits, returns the EXACT locale (no fa fallback — the locale-specific site gives
its own fallback), and null for an unset key.
"""

from __future__ import annotations

from collections.abc import AsyncIterator

import fakeredis.aioredis
import httpx
import pytest_asyncio
from httpx import ASGITransport

from gozar.db.models.content import Content
from gozar.db.models.enums import Language
from gozar.web.app import create_app


def _c(key: str, lang: Language, body: str) -> Content:
    return Content(key=key, language=lang, body=body, link_preview=True)


@pytest_asyncio.fixture
async def copy_client(db_sessions) -> AsyncIterator[httpx.AsyncClient]:
    async with db_sessions() as s:
        s.add_all(
            [
                _c("site_hero_title", Language.fa, "عنوان ویرایش‌شده"),
                _c("site_hero_sub", Language.fa, "زیرتیتر ویرایش‌شده"),
                _c("site_meta_title", Language.fa, "متای ویرایش‌شده"),
                # site_meta_description fa intentionally ABSENT -> null
                _c("site_hero_sub", Language.en, "edited en subtitle"),
                # no en hero_title -> en request must NOT inherit the fa value
            ]
        )
        await s.commit()
    app = create_app()
    app.state.sessionmaker = db_sessions
    app.state.redis = fakeredis.aioredis.FakeRedis(decode_responses=True)
    app.state.panel = None
    async with httpx.AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
        yield c


async def test_returns_edited_fa_copy_and_null_for_absent(copy_client: httpx.AsyncClient) -> None:
    r = await copy_client.get("/api/public/site-copy?locale=fa")
    assert r.status_code == 200
    data = r.json()
    assert data["hero_title"] == "عنوان ویرایش‌شده"
    assert data["hero_sub"] == "زیرتیتر ویرایش‌شده"
    assert data["meta_title"] == "متای ویرایش‌شده"
    assert data["meta_description"] is None  # absent -> null (site falls back to its in-code copy)


async def test_en_does_not_inherit_fa(copy_client: httpx.AsyncClient) -> None:
    r = await copy_client.get("/api/public/site-copy?locale=en")
    assert r.status_code == 200
    data = r.json()
    assert data["hero_sub"] == "edited en subtitle"  # the en row
    # no en hero_title row -> null, NOT the fa text (the en site uses its own en fallback)
    assert data["hero_title"] is None
    assert data["meta_title"] is None


async def test_default_locale_and_invalid_locale(copy_client: httpx.AsyncClient) -> None:
    # default locale is fa
    default = await copy_client.get("/api/public/site-copy")
    assert default.json()["hero_sub"] == "زیرتیتر ویرایش‌شده"
    assert (await copy_client.get("/api/public/site-copy?locale=ru")).status_code == 422
