"""The one error a remote step raises: ``message`` is shown to the admin, ``detail`` holds the raw
output (redacted of secrets), ``code`` lets the console react."""

from __future__ import annotations


class RemoteError(Exception):
    """A step failed. ``code``: "auth" | "network" | "hostkey" | "sudo" | "key" | a panel code |
    None."""

    def __init__(self, message: str, detail: str = "", code: str | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.detail = detail
        self.code = code
