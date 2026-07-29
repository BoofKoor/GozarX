"""Worker fan-out: a broadcast removes a user ONLY on a permanent delivery failure (v1 lesson #4).

``_should_remove`` is the strict allowlist; the ``fanout`` integration test proves a blocked user is
deleted while a transient failure keeps the user.
"""

from __future__ import annotations

from types import SimpleNamespace

from aiogram.exceptions import (
    TelegramBadRequest,
    TelegramForbiddenError,
    TelegramNotFound,
    TelegramRetryAfter,
)

from gozar.db.models.enums import Language
from gozar.worker.tasks import _should_remove, broadcast_text, fanout


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


class _TextBot:
    """Web-broadcast bot: user 2 is blocked (removed), the rest receive the composed text."""

    def __init__(self) -> None:
        self.sent: list[tuple[int, str]] = []

    async def send_message(self, chat_id: int, text: str, parse_mode: str | None = None) -> object:
        if chat_id == 2:
            raise _exc(TelegramForbiddenError, "Forbidden: bot was blocked by the user")
        self.sent.append((chat_id, text))
        return SimpleNamespace(chat=SimpleNamespace(id=chat_id), message_id=1)

    async def edit_message_text(self, text: str, chat_id: int = 0, message_id: int = 0) -> None:
        return None


async def test_broadcast_text_sends_and_removes_blocked(monkeypatch) -> None:
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

    bot = _TextBot()
    ctx = {"bot": bot, "sessionmaker": lambda: FakeSession()}
    await broadcast_text(ctx, "<b>hello</b>", admin_id=999)

    assert removed == [2]  # only the blocked user is dropped
    assert (1, "<b>hello</b>") in bot.sent and (3, "<b>hello</b>") in bot.sent


def _retry(retry_after: int) -> TelegramRetryAfter:
    exc = TelegramRetryAfter.__new__(TelegramRetryAfter)
    exc.message = "Too Many Requests: retry after"
    exc.retry_after = retry_after
    return exc


class _FloodBot:
    """User 5 floods ONCE then succeeds (a flood is transient — retry, don't drop). User 6 floods
    forever (after the back-off + one retry it's kept, never removed — a flood is not a block)."""

    def __init__(self) -> None:
        self.sent: list[int] = []
        self.calls: dict[int, int] = {}

    async def send_message(self, chat_id: int, text: str, parse_mode: str | None = None) -> object:
        self.calls[chat_id] = self.calls.get(chat_id, 0) + 1
        if chat_id == 5 and self.calls[chat_id] == 1:
            raise _retry(1)
        if chat_id == 6:
            raise _retry(1)
        self.sent.append(chat_id)
        return SimpleNamespace(chat=SimpleNamespace(id=chat_id), message_id=1)

    async def edit_message_text(self, text: str, chat_id: int = 0, message_id: int = 0) -> None:
        return None


async def test_broadcast_flood_is_retried_not_dropped(monkeypatch) -> None:
    class FakeRepo:
        def __init__(self, session: object) -> None:
            pass

        async def list_all_ids(self) -> list[int]:
            return [1, 5, 6, 7]

        async def delete(self, telegram_id: int) -> None:
            raise AssertionError("a flood-controlled user must NEVER be removed")

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

    bot = _FloodBot()
    ctx = {"bot": bot, "sessionmaker": lambda: FakeSession()}
    await broadcast_text(ctx, "hi", admin_id=999)

    # 1 and 7 send immediately; 5 sends on its post-backoff retry; 6 floods forever but is KEPT.
    # (999 is the admin progress chat — exclude it from the audience assertion.)
    assert {c for c in bot.sent if c != 999} == {1, 5, 7}
    assert bot.calls[5] == 2 and bot.calls[6] == 2  # each flooded user retried exactly once


async def test_broadcast_delivers_whole_audience_across_chunks(monkeypatch) -> None:
    # More users than _CONCURRENCY (20) — every one delivered exactly once across the chunks.
    ids = list(range(1, 51))

    class FakeRepo:
        def __init__(self, session: object) -> None:
            pass

        async def list_all_ids(self) -> list[int]:
            return list(ids)

        async def delete(self, telegram_id: int) -> None:
            return None

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

    bot = _LangBot()
    ctx = {"bot": bot, "sessionmaker": lambda: FakeSession()}
    await broadcast_text(ctx, "sla", admin_id=999)

    delivered = sorted(chat for chat, text in bot.sent if text == "sla")
    assert delivered == ids  # all 50, no drops, no duplicates


class _LangBot:
    """Records every (chat_id, text) it sends — the language-filter test has no removals."""

    def __init__(self) -> None:
        self.sent: list[tuple[int, str]] = []

    async def send_message(self, chat_id: int, text: str, parse_mode: str | None = None) -> object:
        self.sent.append((chat_id, text))
        return SimpleNamespace(chat=SimpleNamespace(id=chat_id), message_id=1)

    async def edit_message_text(self, text: str, chat_id: int = 0, message_id: int = 0) -> None:
        return None


async def test_broadcast_text_targets_only_chosen_languages(monkeypatch) -> None:
    """A language-targeted broadcast pulls the filtered audience (never the full list), and invalid
    codes are dropped before the query."""
    seen_langs: list = []

    class FakeRepo:
        def __init__(self, session: object) -> None:
            pass

        async def list_all_ids(self) -> list[int]:
            raise AssertionError("must use the language-filtered audience, not list_all_ids")

        async def list_ids_by_languages(self, langs: list) -> list[int]:
            seen_langs.append(langs)
            return [10, 11]

        async def delete(self, telegram_id: int) -> None:
            return None

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

    bot = _LangBot()
    ctx = {"bot": bot, "sessionmaker": lambda: FakeSession()}
    await broadcast_text(ctx, "سلام", admin_id=999, languages=["fa", "xx"])  # 'xx' is invalid

    assert seen_langs == [[Language.fa]]  # invalid 'xx' dropped, valid 'fa' kept
    # the message goes only to the filtered audience (progress pings to admin 999 carry other text)
    assert {chat for chat, text in bot.sent if text == "سلام"} == {10, 11}
