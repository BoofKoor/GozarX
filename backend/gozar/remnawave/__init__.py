"""Remnawave panel integration (thin client + tolerant response schemas)."""

from gozar.remnawave.client import RemnawaveClient
from gozar.remnawave.errors import RemnawaveError

__all__ = ["RemnawaveClient", "RemnawaveError"]
