"""Public account handle helpers — a short, human-readable id for a site device (``GZ-7K3F9A``).

The website has no login, so a device's identity is an opaque ``uuid``. That uuid is fine as an
internal key but unfriendly to show or share, so every device also gets a compact **handle**: the
user-facing account id shown on the 'account' page and used as the referral code in invite links.

Lives in the ``db`` layer (no ORM/session deps) so both the repository (mint) and the web identity
layer (resolve a ``?ref=`` handle) can import it without inverting the service→repo direction.

The alphabet drops every visually ambiguous character (``0/O``, ``1/I/L``, ``U``) so a handle can be
read aloud or typed without confusion. The repository pre-checks a candidate against existing rows
before insert, which avoids a collision in the common case; the DB unique index is the authoritative
backstop. A genuine concurrent collision (two transactions independently picking the same handle in
the same instant — ~1 in 7e8 per pair) surfaces as an IntegrityError rather than an auto-retry; at
this alphabet size and traffic it is astronomically unlikely.
"""

from __future__ import annotations

import secrets

# Unambiguous Crockford-style alphabet: no 0/1/I/L/O/U. 30 symbols ^ 6 places ≈ 7.3e8 handles.
_ALPHABET = "23456789ABCDEFGHJKMNPQRSTVWXYZ"
_PREFIX = "GZ-"
_LENGTH = 6


def new_handle() -> str:
    """A fresh candidate handle (``GZ-`` + 6 unambiguous chars). Caller verifies uniqueness."""
    return _PREFIX + "".join(secrets.choice(_ALPHABET) for _ in range(_LENGTH))


def normalize_handle(raw: str) -> str:
    """Canonical form for comparing an incoming handle (e.g. a ``?ref=`` value): upper-cased,
    whitespace-trimmed. Does not validate the charset — a non-existent handle simply won't match."""
    return raw.strip().upper()
