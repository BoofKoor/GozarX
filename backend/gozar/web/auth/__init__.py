"""Admin-panel authentication (single admin, env credentials).

GozarX has exactly one admin, configured via env: ``admin_username`` + ``admin_password_hash``
(bcrypt) + ``admin_jwt_secret``. There is no admins table and no roles — so login verifies a bcrypt
password and issues HS256 JWTs (access + refresh) bound to the ``gozar-admin`` audience. These
exceptions let the routes/dependency map auth failures to the right HTTP status.
"""

from __future__ import annotations


class AdminAuthError(Exception):
    """Base for admin-auth failures."""


class AdminNotConfigured(AdminAuthError):
    """The panel secrets/credentials aren't set yet (→ HTTP 503)."""


class TokenInvalid(AdminAuthError):
    """A JWT couldn't be decoded, was tampered with, expired, or is the wrong type (→ HTTP 401)."""


class BadCredentials(AdminAuthError):
    """Login username/password didn't match (→ HTTP 401)."""


__all__ = ["AdminAuthError", "AdminNotConfigured", "BadCredentials", "TokenInvalid"]
