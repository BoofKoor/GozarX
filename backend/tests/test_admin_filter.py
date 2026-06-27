"""IsOwner gates the admin router to configured owners (settings.owners)."""

from __future__ import annotations

from types import SimpleNamespace

from gozar.bot.filters import IsOwner


def _event(uid: int | None) -> SimpleNamespace:
    return SimpleNamespace(from_user=SimpleNamespace(id=uid) if uid is not None else None)


async def test_owner_passes(monkeypatch) -> None:
    monkeypatch.setattr(
        "gozar.bot.filters.get_settings", lambda: SimpleNamespace(owners=[111, 222])
    )
    assert await IsOwner()(_event(222)) is True


async def test_non_owner_blocked(monkeypatch) -> None:
    monkeypatch.setattr("gozar.bot.filters.get_settings", lambda: SimpleNamespace(owners=[111]))
    assert await IsOwner()(_event(999)) is False


async def test_no_owners_blocks_everyone(monkeypatch) -> None:
    monkeypatch.setattr("gozar.bot.filters.get_settings", lambda: SimpleNamespace(owners=[]))
    assert await IsOwner()(_event(111)) is False


async def test_event_without_user_blocked(monkeypatch) -> None:
    monkeypatch.setattr("gozar.bot.filters.get_settings", lambda: SimpleNamespace(owners=[111]))
    assert await IsOwner()(_event(None)) is False
