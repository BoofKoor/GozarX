"""POST /panel-webhook security: disabled -> 503, bad signature -> 403.

Both short-circuit BEFORE any DB access, so no database is needed (the reset/send logic is covered
by the DB-gated test_reminder_service). The success path is exercised live on first deploy.
"""

from __future__ import annotations

from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

from gozar.config.settings import get_settings
from gozar.remnawave.schemas import PanelUser
from gozar.web.app import create_app
from gozar.web.routes.panel import _reminder_tokens


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


def test_reminder_tokens_from_webhook_data() -> None:
    # The reminder "global variables" are filled from the webhook's own user payload.
    data = PanelUser.model_validate(
        {
            "trafficLimitBytes": 2 * 1024**3,
            "userTraffic": {"usedTrafficBytes": 512 * 1024**2},
            "expireAt": "2026-06-30T14:00:00.000Z",
        }
    )
    tokens = _reminder_tokens(data)
    assert tokens["total_traffic"] == "2.0 GB"
    assert tokens["used_traffic"] == "512.0 MB"
    assert tokens["expire"] == "2026-06-30 14:00"  # date+time, trimmed


def test_reminder_tokens_missing_expire() -> None:
    assert _reminder_tokens(PanelUser())["expire"] == "—"  # no expireAt -> placeholder
