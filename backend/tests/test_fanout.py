"""Worker fan-out: a broadcast removes a user ONLY on a permanent delivery failure (v1 lesson #4).

``_should_remove`` is the strict allowlist; the ``fanout`` integration test proves a blocked user is
deleted while a transient failure keeps the user.
"""

from __future__ import annotations

from types import SimpleNamespace

from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError, TelegramNotFound

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
    # aiogram 3: "chat not found" is a TelegramNotFound, NOT a TelegramBadRequest.
    assert _should_remove(_exc(TelegramNotFound, "Not Found: chat not found"))


def test_keep_on_other_forbidden() -> None:
    # A different Forbidden description (e.g. kicked from a group) is NOT a private-chat removal.
    assert not _should_remove(
        _exc(TelegramForbiddenError, "Forbidden: bot was kicked from the chat")
    )


def test_keep_on_cant_initiate_conversation() -> None:
    # The user simply never started the bot — not a real block, so we must NOT remove them.
    assert not _should_remove(
        _exc(TelegramForbiddenError, "Forbidden: bot can't initiate conversation with a user")
    )


def test_keep_on_other_bad_request() -> None:
    assert not _should_remove(_exc(TelegramBadRequest, "Bad Request: message is too long"))


def test_keep_on_generic_error() -> None:
    assert not _should_remove(RuntimeError("network blip"))


class _Bot:
    """Per-user send outcomes: 1 ok · 2 blocked · 3 transient · 4 chat-not-found.

    Users 2 and 4 are removed, 3 is kept. User 4 exercises the except-clause routing:
    TelegramNotFound is a sibling of BadRequest (not a subclass), so it must be named in the removal
    `except` or it falls through to the transient branch and the dead user is wrongly kept.
    """

    async def send_message(self, chat_id: int, text: str) -> SimpleNamespace:
        return SimpleNamespace(chat=SimpleNamespace(id=chat_id), message_id=42)

    async def edit_message_text(self, text: str, chat_id: int = 0, message_id: int = 0) -> None:
        return None

    async def copy_message(self, chat_id: int, from_chat_id: int, message_id: int) -> None:
        if chat_id == 2:
            raise _exc(TelegramForbiddenError, "Forbidden: bot was blocked by the user")
        if chat_id == 3:
            raise RuntimeError("transient send error")
        if chat_id == 4:
            raise _exc(TelegramNotFound, "Not Found: chat not found")
        return None


async def test_fanout_removes_only_permanent_failures(monkeypatch) -> None:
    removed: list[int] = []

    class FakeRepo:
        def __init__(self, session: object) -> None:
            pass

        async def list_all_ids(self) -> list[int]:
            return [1, 2, 3, 4]

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

    # Blocked (2) and chat-not-found (4) are removed; the transient failure (3) keeps the user.
    assert removed == [2, 4]
