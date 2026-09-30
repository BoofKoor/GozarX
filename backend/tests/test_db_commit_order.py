"""``DbSession`` commits BEFORE the response is sent.

FastAPI ends a yield dependency after the response by default, so a failed commit arrived after the
client had already been told "saved". These drive a route whose commit fails and check the client
hears about it.
"""

from __future__ import annotations

import fakeredis.aioredis
import httpx
from fastapi import FastAPI
from httpx import ASGITransport

from gozar.web.dependencies import DbSession


class _Session:
    def __init__(self) -> None:
        self.sync_session = type("S", (), {"info": {}})()
        self.rolled_back = False

    async def commit(self) -> None:
        raise RuntimeError("commit failed")

    async def rollback(self) -> None:
        self.rolled_back = True

    async def __aenter__(self) -> _Session:
        return self

    async def __aexit__(self, *exc: object) -> None:
        return None


async def test_a_failed_commit_is_a_500_not_a_200() -> None:
    app = FastAPI()
    session = _Session()
    app.state.sessionmaker = lambda: session
    app.state.redis = fakeredis.aioredis.FakeRedis(decode_responses=True)

    @app.post("/save")
    async def save(db: DbSession) -> dict[str, bool]:
        return {"saved": True}

    transport = ASGITransport(app=app, raise_app_exceptions=False)
    async with httpx.AsyncClient(transport=transport, base_url="http://t") as client:
        response = await client.post("/save")

    assert response.status_code == 500
    assert session.rolled_back
