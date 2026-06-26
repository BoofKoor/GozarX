"""Webhook route wiring + security through the real app + lifespan (lazy resources, no DB)."""

from __future__ import annotations

from fastapi.testclient import TestClient

from gozar.web.app import create_app


def test_health_and_webhook_rejects_bad_secret() -> None:
    with TestClient(create_app()) as client:
        assert client.get("/health").status_code == 200
        # Wrong secret path segment -> 403 before any bot/dispatch access.
        assert client.post("/tg/badsecret", json={}).status_code == 403
