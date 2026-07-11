"""Application settings — zero import side effects.

Importing this module does nothing observable. Call :func:`get_settings` to read
configuration; it constructs (and caches) the ``Settings`` object on first use,
reading from the process environment and ``.env``.
"""

from __future__ import annotations

from functools import lru_cache
from typing import Annotated

from pydantic import SecretStr, field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict


class Settings(BaseSettings):
    """Infrastructure/secret configuration. Runtime product config lives in the DB."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # ── Telegram bot ──────────────────────────────────────────────────────
    bot_token: SecretStr = SecretStr("")
    bot_username: str = ""
    # Comma-separated Telegram user IDs (parsed below); NoDecode skips JSON decoding.
    owners: Annotated[list[int], NoDecode] = []
    domain: str = ""
    admin_domain: str = ""

    # ── Webhook security ──────────────────────────────────────────────────
    webhook_secret: SecretStr = SecretStr("")
    webhook_header_secret: SecretStr = SecretStr("")
    # Shared secret the Remnawave panel signs its webhooks with (HMAC-SHA256 over the body).
    panel_webhook_secret: SecretStr = SecretStr("")

    # ── Remnawave panel ───────────────────────────────────────────────────
    panel_base_url: str = ""
    panel_api_token: SecretStr = SecretStr("")

    # ── Datastores ────────────────────────────────────────────────────────
    database_url: str = "postgresql+asyncpg://gozar:gozar@postgres:5432/gozar"
    redis_url: str = "redis://redis:6379/0"

    # ── Admin panel / API ─────────────────────────────────────────────────
    admin_jwt_secret: SecretStr = SecretStr("")
    admin_username: str = "admin"
    admin_password_hash: str = ""

    # ── Website (separate product on shared infra) ────────────────────────
    # Public domain the site is served from (root of the domain; the admin SPA moves to /admin).
    site_domain: str = ""
    # HMAC key that signs the httpOnly device-identity cookie (UUID + HMAC). Empty in dev.
    site_cookie_secret: SecretStr = SecretStr("")
    # Cloudflare Turnstile (anti-abuse on the public endpoints). Empty ⇒ verification is skipped
    # (dev/build); production keys are provisioned by the installer. site_key is public.
    turnstile_secret: SecretStr = SecretStr("")
    turnstile_site_key: str = ""
    # Web Push (VAPID). Empty ⇒ push disabled; keys minted by the installer. public key is public.
    vapid_private_key: SecretStr = SecretStr("")
    vapid_public_key: str = ""
    vapid_subject: str = ""  # mailto: or https: contact for the VAPID 'sub' claim.

    # ── Misc ──────────────────────────────────────────────────────────────
    log_level: str = "INFO"
    log_json: bool = False
    tz: str = "UTC"
    backup_channel_id: str = ""

    @field_validator("owners", mode="before")
    @classmethod
    def _parse_owners(cls, value: object) -> object:
        if isinstance(value, str):
            return [int(part) for part in value.split(",") if part.strip()]
        return value


@lru_cache
def get_settings() -> Settings:
    """Return the cached ``Settings`` instance (reads env/.env on first call only)."""
    return Settings()
