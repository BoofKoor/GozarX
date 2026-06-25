"""Phase 0 acceptance gate: the app factory boots and /health returns 200."""

from __future__ import annotations

import httpx

from gozar.web.app import create_app


async def test_health_ok() -> None:
    transport = httpx.ASGITransport(app=create_app())
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
