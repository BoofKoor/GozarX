"""Worker fan-out: a broadcast removes a user ONLY on a permanent delivery failure (v1 lesson #4).

``_should_remove`` is the strict allowlist; the ``fanout`` integration test proves a blocked user is
deleted while a transient failure keeps the user.
"""

from __future__ import annotations

from types import SimpleNamespace

from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError

from gozar.worker.tasks import _should_remove, fanout


def _exc(cls: type, message: str) -> Exception:
    """A real aiogram exception instance with a set ``.message`` (bypasses the API constructor)."""
    exc = cls.__new__(cls)
    exc.message = message
    return exc


def test_remove_on_blocked() -> None:
    assert _should_remove(_exc(TelegramForbiddenError, "Forbidden: bot was blocked by the user"))


def test_remove_on_deactivated() -> None:
    assert _should_remove(_exc(TelegramForbiddenError, "Forbidden: user is deactivated"))


def test_remove_on_chat_not_found() -> None:
    assert _should_remove(_exc(TelegramBadRequest, "Bad Request: chat not found"))


def test_keep_on_other_forbidden() -> None:
    # A different Forbidden description (e.g. kicked from a group) is NOT a private-chat removal.
    assert not _should_remove(
        _exc(TelegramForbiddenError, "Forbidden: bot was kicked from the chat")
    )


def test_keep_on_other_bad_request() -> None:
    assert not _should_remove(_exc(TelegramBadRequest, "Bad Request: message is too long"))


def test_keep_on_generic_error() -> None:
    assert not _should_remove(RuntimeError("network blip"))


class _Bot:
    """Per-user delivery outcomes: 1 ok · 2 blocked (remove) · 3 transient (keep)."""

    async def send_message(self, chat_id: int, text: str) -> SimpleNamespace:
        return SimpleNamespace(chat=SimpleNamespace(id=chat_id), message_id=42)

    async def edit_message_text(self, text: str, chat_id: int = 0, message_id: int = 0) -> None:
        return None

    async def copy_message(self, chat_id: int, from_chat_id: int, message_id: int) -> None:
        if chat_id == 2:
            raise _exc(TelegramForbiddenError, "Forbidden: bot was blocked by the user")
        if chat_id == 3:
            raise RuntimeError("transient send error")
        return None


async def test_fanout_removes_only_permanent_failures(monkeypatch) -> None:
    removed: list[int] = []

    class FakeRepo:
        def __init__(self, session: object) -> None:
            pass

        async def list_all_ids(self) -> list[int]:
            return [1, 2, 3]

        async def delete(self, telegram_id: int) -> None:
            removed.append(telegram_id)

    class FakeSession:
        async def __aenter__(self) -> FakeSession:
            return self

        async def __aexit__(self, *exc: object) -> bool:
            return False

        async def commit(self) -> None:
            return None

    async def _noop(*args: object, **kwargs: object) -> None:
        return None

    monkeypatch.setattr("gozar.worker.tasks.UserRepository", FakeRepo)
    monkeypatch.setattr("gozar.worker.tasks.asyncio.sleep", _noop)

    ctx = {"bot": _Bot(), "sessionmaker": lambda: FakeSession()}
    await fanout(ctx, "broadcast", chat_id=100, message_id=200, admin_id=999)

    # Only the blocked user (2) is removed; the transient failure (3) keeps the user.
    assert removed == [2]
