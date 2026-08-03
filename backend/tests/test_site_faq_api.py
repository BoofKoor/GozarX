"""Website FAQ — admin CRUD + the public read endpoint (DB-gated).

Same wiring as ``test_site_admin_api.py``: the real routes over httpx + ASGITransport with
``app.state`` set directly. Skipped without ``TEST_DATABASE_URL``.
"""

from __future__ import annotations

from collections.abc import AsyncIterator

import fakeredis.aioredis
import httpx
import pytest_asyncio
from httpx import ASGITransport

from gozar.config.settings import get_settings
from gozar.db.repositories.site_faq_item import SiteFaqItemRepository
from gozar.seed_faq import DEFAULT_SITE_FAQ
from gozar.web.app import create_app
from gozar.web.auth.jwt import create_access

_SECRET = "test-admin-secret-0123456789-abcdef-ghijkl"  # >=32 bytes for PyJWT

_ITEM = {
    "locale": "fa",
    "category": "start",
    "question": "چطور شروع کنم؟",
    "answer": "لوکیشن را انتخاب کن و دکمه را بزن.",
}


def _build_app(db_sessions):
    app = create_app()
    app.state.sessionmaker = db_sessions
    app.state.redis = fakeredis.aioredis.FakeRedis(decode_responses=True)
    app.state.panel = None
    app.state.arq = None
    return app


@pytest_asyncio.fixture
async def client(db_sessions, monkeypatch) -> AsyncIterator[httpx.AsyncClient]:
    monkeypatch.setenv("ADMIN_JWT_SECRET", _SECRET)
    monkeypatch.setenv("ADMIN_USERNAME", "root")
    get_settings.cache_clear()
    token = create_access("root")
    async with httpx.AsyncClient(
        transport=ASGITransport(app=_build_app(db_sessions)),
        base_url="http://t",
        headers={"Authorization": f"Bearer {token}"},
    ) as c:
        yield c
    get_settings.cache_clear()


async def test_faq_requires_auth(client: httpx.AsyncClient) -> None:
    assert (
        await client.get("/api/admin/site/faq/", headers={"Authorization": ""})
    ).status_code == 401


async def test_faq_crud_flow(client: httpx.AsyncClient) -> None:
    created = await client.post("/api/admin/site/faq/", json=_ITEM)
    assert created.status_code == 201
    item_id = created.json()["id"]
    assert created.json()["published"] is True

    # The same question in the same language is a duplicate; in the other language it isn't.
    assert (await client.post("/api/admin/site/faq/", json=_ITEM)).status_code == 409
    assert (
        await client.post(
            "/api/admin/site/faq/", json={**_ITEM, "locale": "en", "question": "How do I start?"}
        )
    ).status_code == 201

    assert len((await client.get("/api/admin/site/faq/")).json()) == 2
    assert len((await client.get("/api/admin/site/faq/?locale=fa")).json()) == 1

    upd = await client.put(
        f"/api/admin/site/faq/{item_id}", json={**_ITEM, "answer": "پاسخ تازه", "published": False}
    )
    assert upd.status_code == 200 and upd.json()["answer"] == "پاسخ تازه"

    assert (await client.delete(f"/api/admin/site/faq/{item_id}")).status_code == 204
    assert (await client.delete(f"/api/admin/site/faq/{item_id}")).status_code == 404


async def test_faq_rejects_a_category_the_site_cannot_render(client: httpx.AsyncClient) -> None:
    """The site builds its tabs from a fixed category set.

    An item filed under anything else would only appear under "all" — from the operator's side it
    would look like the answer they just wrote had vanished from its section.
    """
    r = await client.post("/api/admin/site/faq/", json={**_ITEM, "category": "billing"})
    assert r.status_code == 422
    assert "start" in r.json()["detail"]  # the message names what IS allowed
    assert (
        await client.post("/api/admin/site/faq/", json={**_ITEM, "locale": "ru"})
    ).status_code == 422


async def test_new_items_go_to_the_end_not_the_top(client: httpx.AsyncClient) -> None:
    """A new question must not reorder a list the operator already arranged."""
    for n in range(3):
        r = await client.post("/api/admin/site/faq/", json={**_ITEM, "question": f"پرسش {n}"})
        assert r.status_code == 201
    positions = [i["position"] for i in (await client.get("/api/admin/site/faq/")).json()]
    assert positions == [0, 1, 2]


async def test_reorder_applies_the_whole_order_or_none_of_it(client: httpx.AsyncClient) -> None:
    ids = [
        (await client.post("/api/admin/site/faq/", json={**_ITEM, "question": f"پرسش {n}"})).json()[
            "id"
        ]
        for n in range(3)
    ]

    reordered = await client.put("/api/admin/site/faq/reorder", json={"ids": list(reversed(ids))})
    assert reordered.status_code == 200
    assert [i["id"] for i in reordered.json()] == list(reversed(ids))

    # A stale list (an id that no longer exists) is rejected outright — applying the surviving part
    # would silently reshuffle the items that DO exist.
    stale = await client.put("/api/admin/site/faq/reorder", json={"ids": [*ids, 999_999]})
    assert stale.status_code == 409
    assert [i["id"] for i in (await client.get("/api/admin/site/faq/")).json()] == list(
        reversed(ids)
    )


async def test_public_faq_returns_published_items_in_order(client: httpx.AsyncClient) -> None:
    ids = [
        (await client.post("/api/admin/site/faq/", json={**_ITEM, "question": f"پرسش {n}"})).json()[
            "id"
        ]
        for n in range(3)
    ]
    await client.put(
        f"/api/admin/site/faq/{ids[1]}",
        json={**_ITEM, "question": "پرسش 1", "published": False},
    )
    await client.post("/api/admin/site/faq/", json={**_ITEM, "locale": "en", "question": "en one"})

    body = (await client.get("/api/public/faq?locale=fa")).json()
    # The shape mirrors the site's in-code FaqItem so the renderer needs no branch.
    assert body == [
        {"cat": "start", "q": "پرسش 0", "a": _ITEM["answer"]},
        {"cat": "start", "q": "پرسش 2", "a": _ITEM["answer"]},
    ]
    assert [i["q"] for i in (await client.get("/api/public/faq?locale=en")).json()] == ["en one"]
    assert (await client.get("/api/public/faq?locale=ru")).status_code == 422


async def test_public_faq_is_open(client: httpx.AsyncClient) -> None:
    # No admin JWT: the site renders this server-side with no credentials at all.
    r = await client.get("/api/public/faq", headers={"Authorization": ""})
    assert r.status_code == 200


async def test_seed_defaults_are_idempotent(db_sessions) -> None:
    """Re-running the seeder must not duplicate an item, nor undo an operator's edit."""
    async with db_sessions() as s:
        repo = SiteFaqItemRepository(s)
        for item in DEFAULT_SITE_FAQ:
            await repo.add_default(**item)  # type: ignore[arg-type]
        await s.commit()

    async with db_sessions() as s:
        repo = SiteFaqItemRepository(s)
        first = await repo.list()
        assert len(first) == len(DEFAULT_SITE_FAQ)
        edited = first[0]
        await repo.update(
            edited,
            locale=edited.locale,
            category=edited.category,
            question=edited.question,
            answer="پاسخ ویرایش‌شده",
            position=edited.position,
            published=False,
        )
        await s.commit()

    async with db_sessions() as s:
        repo = SiteFaqItemRepository(s)
        for item in DEFAULT_SITE_FAQ:
            await repo.add_default(**item)  # type: ignore[arg-type]
        await s.commit()

    async with db_sessions() as s:
        again = await SiteFaqItemRepository(s).list()
        assert len(again) == len(DEFAULT_SITE_FAQ)  # no duplicates
        kept = next(i for i in again if i.id == edited.id)
        assert kept.answer == "پاسخ ویرایش‌شده" and kept.published is False
