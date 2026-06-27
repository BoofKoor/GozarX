"""Admin JWTs (PyJWT, HS256).

Two tokens per login: a short-lived **access** token (Authorization: Bearer) and a long-lived
**refresh** token that mints new access tokens. Both are signed with ``admin_jwt_secret`` and bound
to the ``gozar-admin`` audience — a token minted for any other context (or with no audience) is
rejected on decode. ``decode`` also enforces the token *type*, so a refresh token can never be used
as an access token. The secret is read at call time via ``get_settings()`` (never at import).
"""

from __future__ import annotations

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
TYPE_ACCESS = "access"
TYPE_REFRESH = "refresh"


@dataclass(frozen=True)
class TokenPayload:
    sub: str
    type: str
    issued_at: int
    expires_at: int
    jti: str


def _secret() -> str:
    secret = get_settings().admin_jwt_secret.get_secret_value()
    if not secret:
        raise AdminNotConfigured("admin_jwt_secret is not set")
    return secret


def _encode(sub: str, token_type: str, ttl: int) -> str:
    now = int(time.time())
    payload = {
        "sub": sub,
        "typ": token_type,
        "aud": _AUDIENCE,
        "iat": now,
        "exp": now + ttl,
        "jti": uuid.uuid4().hex,
    }
    return jwt.encode(payload, _secret(), algorithm=_ALGORITHM)


def create_access(subject: str) -> str:
    return _encode(subject, TYPE_ACCESS, ACCESS_TTL)


def create_refresh(subject: str) -> str:
    return _encode(subject, TYPE_REFRESH, REFRESH_TTL)


def decode(token: str, expected_type: str) -> TokenPayload:
    """Verify signature + audience + expiry, then enforce the token type. Raises ``TokenInvalid``
    on any mismatch and ``AdminNotConfigured`` if the signing secret isn't set."""
    try:
        data = jwt.decode(token, _secret(), algorithms=[_ALGORITHM], audience=_AUDIENCE)
    except InvalidTokenError as exc:
        raise TokenInvalid(str(exc)) from exc
    if data.get("typ") != expected_type:
        raise TokenInvalid(f"expected {expected_type} token")
    return TokenPayload(
        sub=str(data.get("sub", "")),
        type=str(data.get("typ", "")),
        issued_at=int(data.get("iat", 0)),
        expires_at=int(data.get("exp", 0)),
        jti=str(data.get("jti", "")),
    )
