"""POST /panel-webhook security: disabled -> 503, bad signature -> 403.

Both short-circuit BEFORE any DB access, so no database is needed (the reset/send logic is covered
by the DB-gated test_reminder_service). The success path is exercised live on first deploy.
"""

from __future__ import annotations

from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

from gozar.config.settings import get_settings
from gozar.web.app import create_app


@pytest.fixture(autouse=True)
def _reset_settings_cache() -> Iterator[None]:
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def test_panel_webhook_disabled_returns_503(monkeypatch) -> None:
    monkeypatch.setenv("PANEL_WEBHOOK_SECRET", "")
    with TestClient(create_app()) as client:
        assert client.post("/panel-webhook", content=b"{}").status_code == 503


def test_panel_webhook_bad_signature_returns_403(monkeypatch) -> None:
    monkeypatch.setenv("PANEL_WEBHOOK_SECRET", "topsecret")
    with TestClient(create_app()) as client:
        resp = client.post(
            "/panel-webhook",
            content=b'{"event":"user.expired","data":{"username":"x"}}',
            headers={"x-remnawave-signature": "deadbeef"},
        )
        assert resp.status_code == 403
