"""Remnawave client errors."""

from __future__ import annotations


class RemnawaveError(Exception):
    """A single bounded panel call failed (network error, non-2xx, or unparseable response)."""

    def __init__(self, message: str, *, status_code: int | None = None) -> None:
        super().__init__(message)
        self.status_code = status_code
