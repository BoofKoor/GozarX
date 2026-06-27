"""Admin password hashing/verification (bcrypt).

The installer (Phase 9) mints ``admin_password_hash`` once and writes it to ``.env``; login verifies
against it. Run ``python -m gozar.web.auth.passwords`` to generate a hash for a password you type
(nothing is echoed, and the password never touches argv).
"""

from __future__ import annotations

import bcrypt

from gozar.web.auth import AdminNotConfigured


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, hashed: str) -> bool:
    """True iff ``password`` matches the bcrypt ``hashed``. Raises ``AdminNotConfigured`` when no
    hash is set; returns False (never raises) on a malformed stored hash."""
    if not hashed:
        raise AdminNotConfigured("admin_password_hash is not set")
    try:
        return bcrypt.checkpw(password.encode("utf-8"), hashed.encode("utf-8"))
    except ValueError:
        return False


def _main() -> None:
    import getpass

    password = getpass.getpass("Admin password: ")
    if password != getpass.getpass("Confirm password: "):
        raise SystemExit("passwords did not match")
    print(hash_password(password))  # noqa: T201 — this CLI's only job is to print the hash


if __name__ == "__main__":
    _main()
