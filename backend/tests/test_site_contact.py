"""P6 — contact form: POST /contact writes a ``site_messages`` row (the admin 'website' inbox, P9).

Endpoint-driven against the real ASGI app (Turnstile is skipped in tests — unconfigured secret),
plus a direct repository test. The message is the only required field; Topic + reply handle are
optional per the zero-signup design.
"""

from __future__ import annotations

import json
from collections.abc import AsyncIterator

import fakeredis.aioredis
import httpx
import pytest_asyncio
from httpx import ASGITransport
from sqlalchemy import select

from gozar.cache.redis import SETTINGS_KEY
from gozar.config.settings import get_settings
from gozar.db.models.site_message import SiteMessage
from gozar.db.repositories.site_message import SiteMessageRepository
from gozar.web.app import create_app

_SETTINGS = {"site_daily_limit_mb": "1024"}


# --- repository ---------------------------------------------------------------------------------


async def test_message_repo_add_inserts_row(session) -> None:
    repo = SiteMessageRepository(session)
    msg = await repo.add(
        subject="Report a bug",
        body="the config link 404s",
        reply_handle="me@example.com",
        locale="en",
        device_uuid="dev-1",
    )
    assert msg.id is not None
    stored = await session.get(SiteMessage, msg.id)
    assert stored.subject == "Report a bug"
    assert stored.body == "the config link 404s"
    assert stored.reply_handle == "me@example.com"
    assert stored.locale == "en"
    assert stored.device_uuid == "dev-1"
    assert stored.read is False  # server_default


# --- endpoint -----------------------------------------------------------------------------------


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


async def test_contact_stores_message(env, db_sessions) -> None:
    client, _app = env
    resp = await client.post(
        "/api/public/contact",
        json={"subject": "Connection issue", "body": "can't connect from Iran", "locale": "fa"},
    )
    assert resp.status_code == 200 and resp.json()["ok"] is True
    async with db_sessions() as s:
        rows = (await s.scalars(select(SiteMessage))).all()
    assert len(rows) == 1
    assert rows[0].subject == "Connection issue"
    assert rows[0].body == "can't connect from Iran"
    assert rows[0].locale == "fa"
    assert rows[0].reply_handle is None
    assert rows[0].device_uuid is not None  # correlated to the minted device


async def test_contact_message_is_only_required_field(env, db_sessions) -> None:
    client, _app = env
    # No subject, no reply handle — just a message. Stored with the default subject.
    resp = await client.post("/api/public/contact", json={"body": "just a note"})
    assert resp.json()["ok"] is True
    async with db_sessions() as s:
        row = (await s.scalars(select(SiteMessage))).one()
    assert row.subject == "general"
    assert row.reply_handle is None


async def test_contact_empty_body_rejected(env) -> None:
    client, _app = env
    assert (await client.post("/api/public/contact", json={"body": ""})).status_code == 422
    assert (await client.post("/api/public/contact", json={"body": "   "})).status_code == 422
    assert (await client.post("/api/public/contact", json={"subject": "x"})).status_code == 422


async def test_contact_reply_handle_blank_becomes_null(env, db_sessions) -> None:
    client, _app = env
    await client.post("/api/public/contact", json={"body": "hi", "reply_handle": "   "})
    async with db_sessions() as s:
        row = (await s.scalars(select(SiteMessage))).one()
    assert row.reply_handle is None


async def test_contact_invalid_locale_coerced_to_fa(env, db_sessions) -> None:
    client, _app = env
    await client.post("/api/public/contact", json={"body": "hi", "locale": "xx"})
    async with db_sessions() as s:
        row = (await s.scalars(select(SiteMessage))).one()
    assert row.locale == "fa"


async def test_contact_rate_limited(env, db_sessions) -> None:
    client, _app = env
    # _CONTACT_LIMIT = 5 per window; the 6th on the same device cookie is throttled.
    for _ in range(5):
        assert (await client.post("/api/public/contact", json={"body": "hi"})).status_code == 200
    assert (await client.post("/api/public/contact", json={"body": "hi"})).status_code == 429
    async with db_sessions() as s:
        rows = (await s.scalars(select(SiteMessage))).all()
    assert len(rows) == 5  # the throttled request stored nothing
