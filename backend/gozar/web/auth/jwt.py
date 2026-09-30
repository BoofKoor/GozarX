"""Admin JWTs (PyJWT, HS256).

Two tokens per login: a short-lived **access** token (Authorization: Bearer) and a long-lived
**refresh** token that mints new access tokens. Both are signed with ``admin_jwt_secret`` and bound
to the ``gozar-admin`` audience — a token minted for any other context (or with no audience) is
rejected on decode. ``decode`` also enforces the token *type*, so a refresh token can never be used
as an access token. The secret is read at call time via ``get_settings()`` (never at import).

Two things bound a session beyond each token's own expiry:

* **A credential version** (``cv``): a keyed fingerprint of the admin's CURRENT username and
  password hash. Changing the password (``python -m gozar.web.auth.passwords`` + a restart) changes
  it, and every token minted under the old credentials stops verifying. Before this, a password
  change left every existing session — including a leaked one — working for up to seven more days,
  and a refresh renewed it indefinitely. Keyed with the signing secret, so the claim says nothing
  about the hash itself.
* **An absolute session age** (``auth_time``): the login's own timestamp, carried unchanged through
  every refresh, with a refresh token never outliving ``SESSION_MAX`` after it. A rotated refresh
  token used to buy another seven days each time, so one stolen token was a session forever.
"""

from __future__ import annotations

import hashlib
import hmac
import time
import uuid
from dataclasses import dataclass

import jwt
from jwt import InvalidTokenError

from gozar.config.settings import get_settings
from gozar.web.auth import AdminNotConfigured, TokenInvalid

_ALGORITHM = "HS256"
_AUDIENCE = "gozar-admin"
ACCESS_TTL = 3600  # 1 hour
REFRESH_TTL = 7 * 24 * 3600  # 7 days
#: However often it is refreshed, a login lasts at most this long; then the admin signs in again.
SESSION_MAX = 30 * 24 * 3600  # 30 days
TYPE_ACCESS = "access"
TYPE_REFRESH = "refresh"


@dataclass(frozen=True)
class TokenPayload:
    sub: str
    type: str
    issued_at: int
    expires_at: int
    jti: str
    auth_time: int  # when the session's LOGIN happened — unchanged by a refresh


def _secret() -> str:
    secret = get_settings().admin_jwt_secret.get_secret_value()
    if not secret:
        raise AdminNotConfigured("admin_jwt_secret is not set")
    return secret


def credential_version() -> str:
    """A keyed fingerprint of the admin's current credentials — see the module docstring."""
    settings = get_settings()
    material = f"{settings.admin_username}\n{settings.admin_password_hash}".encode()
    return hmac.new(_secret().encode(), material, hashlib.sha256).hexdigest()[:32]


def _encode(sub: str, token_type: str, ttl: int, auth_time: int | None) -> str:
    now = int(time.time())
    started = auth_time if auth_time is not None else now
    payload = {
        "sub": sub,
        "typ": token_type,
        "aud": _AUDIENCE,
        "iat": now,
        # Never past the session's absolute end, whatever the token's own lifetime would allow.
        "exp": min(now + ttl, started + SESSION_MAX),
        "jti": uuid.uuid4().hex,
        "cv": credential_version(),
        "auth_time": started,
    }
    return jwt.encode(payload, _secret(), algorithm=_ALGORITHM)


def create_access(subject: str, *, auth_time: int | None = None) -> str:
    """``auth_time`` is the login being continued (a refresh); omitted, the token starts one."""
    return _encode(subject, TYPE_ACCESS, ACCESS_TTL, auth_time)


def create_refresh(subject: str, *, auth_time: int | None = None) -> str:
    return _encode(subject, TYPE_REFRESH, REFRESH_TTL, auth_time)


def decode(token: str, expected_type: str) -> TokenPayload:
    """Verify signature + audience + expiry, then enforce the token type. Raises ``TokenInvalid``
    on any mismatch and ``AdminNotConfigured`` if the signing secret isn't set."""
    try:
        data = jwt.decode(token, _secret(), algorithms=[_ALGORITHM], audience=_AUDIENCE)
    except InvalidTokenError as exc:
        raise TokenInvalid(str(exc)) from exc
    if data.get("typ") != expected_type:
        raise TokenInvalid(f"expected {expected_type} token")
    # Minted under other credentials (the password changed since), or before sessions carried a
    # version at all: either way not a session the CURRENT admin opened.
    if not hmac.compare_digest(str(data.get("cv", "")), credential_version()):
        raise TokenInvalid("credentials changed since this token was issued")
    auth_time = int(data.get("auth_time", 0))
    if auth_time <= 0 or time.time() - auth_time > SESSION_MAX:
        raise TokenInvalid("session too old — sign in again")
    return TokenPayload(
        sub=str(data.get("sub", "")),
        type=str(data.get("typ", "")),
        issued_at=int(data.get("iat", 0)),
        expires_at=int(data.get("exp", 0)),
        jti=str(data.get("jti", "")),
        auth_time=auth_time,
    )
