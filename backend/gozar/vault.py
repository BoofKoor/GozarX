"""Secrets at rest: AES-256-GCM under ``VAULT_KEY``.

What the console's operations must keep in the database — the bot's own SSH private key, and the
sudo password of a server whose sudo asks for one — is stored SEALED: a nonce and the ciphertext,
bound by its ``purpose`` (the associated data) to where it belongs, so a value copied into another
row or another column fails to open instead of being used there. The key lives only in ``.env``
(chmod 600, made by the installer, never rotated), so a database dump — the nightly pg_dump sent to
Telegram included — holds nothing usable on its own.

SSH LOGIN passwords are never sealed or stored anywhere: one is used for a single login that
installs the bot's own key, then forgotten (``services/ops`` hands it to the worker through a
short-lived, read-once Redis entry, sealed like this).
"""

from __future__ import annotations

import base64
import binascii
import secrets

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from gozar.config.settings import get_settings

PREFIX = "gv1:"


class VaultError(Exception):
    """The vault can't be used: no/invalid ``VAULT_KEY``, or a value that doesn't open."""


def parse_key(text: str) -> bytes:
    """``VAULT_KEY``: 32 random bytes in base64 (standard or url-safe, padding optional)."""
    t = text.strip()
    t += "=" * (-len(t) % 4)
    try:
        raw = base64.urlsafe_b64decode(t.replace("+", "-").replace("/", "_"))
    except (binascii.Error, ValueError) as e:
        raise VaultError("VAULT_KEY is not valid base64") from e
    if len(raw) != 32:
        raise VaultError(f"VAULT_KEY must be 32 bytes (got {len(raw)})")
    return raw


def new_key_text() -> str:
    """A fresh ``VAULT_KEY`` value (what the installer writes)."""
    return base64.urlsafe_b64encode(secrets.token_bytes(32)).decode()


def _key(key: bytes | None) -> bytes:
    if key is not None:
        return key
    text = get_settings().vault_key.get_secret_value()
    if not text:
        raise VaultError("VAULT_KEY is not set")
    return parse_key(text)


def available() -> bool:
    try:
        _key(None)
    except VaultError:
        return False
    return True


def seal(plaintext: str, purpose: str, *, key: bytes | None = None) -> str:
    nonce = secrets.token_bytes(12)
    data = AESGCM(_key(key)).encrypt(nonce, plaintext.encode(), purpose.encode())
    return PREFIX + base64.urlsafe_b64encode(nonce + data).decode()


def unseal(token: str, purpose: str, *, key: bytes | None = None) -> str:
    if not token.startswith(PREFIX):
        raise VaultError("not a sealed value")
    try:
        blob = base64.urlsafe_b64decode(token[len(PREFIX) :])
    except (binascii.Error, ValueError) as e:
        raise VaultError("damaged sealed value") from e
    if len(blob) < 12 + 16:
        raise VaultError("damaged sealed value")
    try:
        return AESGCM(_key(key)).decrypt(blob[:12], blob[12:], purpose.encode()).decode()
    except InvalidTag as e:
        raise VaultError("wrong key, damaged value, or sealed for something else") from e
