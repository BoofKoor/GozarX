"""Webhook secret-path + header verification (constant-time)."""

from __future__ import annotations

from gozar.config.settings import Settings
from gozar.web.routes.telegram import _webhook_authorized


def _settings() -> Settings:
    return Settings(webhook_secret="path-secret", webhook_header_secret="header-secret")


def test_authorized_when_both_match() -> None:
    assert _webhook_authorized("path-secret", "header-secret", _settings()) is True


def test_rejected_on_wrong_path() -> None:
    assert _webhook_authorized("WRONG", "header-secret", _settings()) is False


def test_rejected_on_wrong_header() -> None:
    assert _webhook_authorized("path-secret", "WRONG", _settings()) is False
