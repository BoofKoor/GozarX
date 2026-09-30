"""Worker fan-out: a broadcast marks a user unreachable ONLY on a permanent delivery failure (v1
lesson #4).

``_should_remove`` is the strict allowlist; the ``fanout`` integration test proves a blocked user is
marked unreachable (never deleted — see test_broadcast_unreachable) while a transient failure keeps
the user untouched.
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
    # What Telegram actually sends: a 400, which aiogram raises as TelegramBadRequest. Matching only
    # TelegramNotFound, a gone chat was a "failed" send on every broadcast, forever.
    assert _should_remove(_exc(TelegramBadRequest, "Bad Request: chat not found"))
    # A real 404 is accepted as well.
    assert _should_remove(_exc(TelegramNotFound, "Not Found: chat not found"))


def test_chat_not_found_on_a_copy_is_not_about_the_recipient() -> None:
    # copy_message / forward_message also name the admin's chat as the SOURCE, so their "chat not
    # found" can be about that one — trusted there, one bad source marks the entire audience.
    for cls, msg in (
        (TelegramBadRequest, "Bad Request: chat not found"),
        (TelegramNotFound, "Not Found: chat not found"),
    ):
        assert not _should_remove(_exc(cls, msg), names_source_chat=True)
    # Blocked / deactivated can only be about the recipient, so they still count on a copy.
    blocked = _exc(TelegramForbiddenError, "Forbidden: bot was blocked by the user")
    assert _should_remove(blocked, names_source_chat=True)


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
    """Per-user send outcomes: 1 ok · 2 blocked · 3 transient · 4 chat-not-found (404) · 5 chat-not-
    found as Telegram really sends it (400) · 6 another bad request.

    This is ``copy_message`` — the bot's own fan-out — so only 2 is marked: a copy names the admin's
    chat as its source, and "chat not found" (4, 5) may be about that chat rather than the user.
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
        if chat_id == 5:
            raise _exc(TelegramBadRequest, "Bad Request: chat not found")
        if chat_id == 6:
            raise _exc(TelegramBadRequest, "Bad Request: message is too long")
        return None


async def test_fanout_removes_only_permanent_failures(monkeypatch) -> None:
    removed: list[int] = []

    class FakeRepo:
        def __init__(self, session: object) -> None:
            pass

        async def list_all_ids(self) -> list[int]:
            return [1, 2, 3, 4, 5, 6]

        async def mark_unreachable(self, telegram_ids: list[int], at: object) -> int:
            removed.extend(telegram_ids)
            return len(telegram_ids)

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

    # Blocked (2) is marked. Chat-not-found (4, 5) is ambiguous on a copy, so it counts as a failed
    # send — as do the transient failure (3) and the unrelated bad request (6).
    assert sorted(removed) == [2]


class _TextBot:
    """Web-broadcast bot: user 2 is blocked and user 4's chat is gone (both marked); the rest
    receive the composed text."""

    def __init__(self) -> None:
        self.sent: list[tuple[int, str]] = []

    async def send_message(
        self, chat_id: int, text: str, parse_mode: str | None = None, **kw: object
    ) -> object:
        if chat_id == 2:
            raise _exc(TelegramForbiddenError, "Forbidden: bot was blocked by the user")
        if chat_id == 4:
            # A direct send names only the recipient, so here "chat not found" is about them.
            raise _exc(TelegramBadRequest, "Bad Request: chat not found")
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
            return [1, 2, 3, 4]

        async def audience_ids(self, langs=None, **kw) -> list[int]:
            return [1, 2, 3, 4]

        async def mark_unreachable(self, telegram_ids: list[int], at: object) -> int:
            removed.extend(telegram_ids)
            return len(telegram_ids)

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

    assert sorted(removed) == [2, 4]  # the blocked user and the gone chat, nobody else
    assert (1, "<b>hello</b>") in bot.sent and (3, "<b>hello</b>") in bot.sent


async def test_gone_chats_are_marked_as_the_send_goes(monkeypatch) -> None:
    """Marked at every checkpoint, not once at the end: a job cancelled mid-send — every deploy
    restarts the worker — counted its gone chats in the log row and marked none of them."""
    batches: list[list[int]] = []

    class FakeRepo:
        def __init__(self, session: object) -> None:
            pass

        async def audience_ids(self, langs=None, **kw) -> list[int]:
            return list(range(1, 46))

        async def mark_unreachable(self, telegram_ids: list[int], at: object) -> int:
            batches.append(list(telegram_ids))
            return len(telegram_ids)

    class FakeSession:
        async def __aenter__(self) -> FakeSession:
            return self

        async def __aexit__(self, *exc: object) -> bool:
            return False

        async def commit(self) -> None:
            return None

    class GoneBot(_LangBot):
        async def send_message(self, chat_id: int, text: str, *a: object, **kw: object) -> object:
            if chat_id in (3, 25):
                raise _exc(TelegramForbiddenError, "Forbidden: bot was blocked by the user")
            return await super().send_message(chat_id, text, *a, **kw)

    async def _noop(*args: object, **kwargs: object) -> None:
        return None

    monkeypatch.setattr("gozar.worker.tasks.UserRepository", FakeRepo)
    monkeypatch.setattr("gozar.worker.tasks.asyncio.sleep", _noop)
    monkeypatch.setattr("gozar.worker.tasks._CHECKPOINT_EVERY", 20)

    ctx = {"bot": GoneBot(), "sessionmaker": lambda: FakeSession()}
    await broadcast_text(ctx, "hi", admin_id=999)

    # One mark per checkpoint (after 20 and 40 sends), each carrying only what it found; nothing is
    # left over for the final pass, and nobody is marked twice.
    assert batches == [[3], [25]]


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

    async def send_message(
        self, chat_id: int, text: str, parse_mode: str | None = None, **kw: object
    ) -> object:
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

        async def audience_ids(self, langs=None, **kw) -> list[int]:
            return [1, 5, 6, 7]

        async def mark_unreachable(self, telegram_ids: list[int], at: object) -> int:
            if telegram_ids:
                raise AssertionError("a flood-controlled user must NEVER be removed")
            return 0

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

        async def audience_ids(self, langs=None, **kw) -> list[int]:
            return list(ids)

        async def mark_unreachable(self, telegram_ids: list[int], at: object) -> int:
            return len(telegram_ids)

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

    async def send_message(
        self, chat_id: int, text: str, parse_mode: str | None = None, **kw: object
    ) -> object:
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
            raise AssertionError("the panel broadcast goes through audience_ids")

        async def audience_ids(self, langs=None, **kw) -> list[int]:
            seen_langs.append(langs)
            seen_langs.append(kw)
            return [10, 11]

        async def mark_unreachable(self, telegram_ids: list[int], at: object) -> int:
            return len(telegram_ids)

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

    # invalid 'xx' dropped, valid 'fa' kept — and the two audience refinements default to off.
    assert seen_langs == [[Language.fa], {"only_active": False, "only_referrers": False}]
    # the message goes only to the filtered audience (progress pings to admin 999 carry other text)
    assert {chat for chat, text in bot.sent if text == "سلام"} == {10, 11}


async def test_broadcast_attaches_the_inline_keyboard_and_narrows_the_audience(monkeypatch) -> None:
    """The composer's buttons reach Telegram, and its refinements reach the audience query.

    Both are things the operator was shown before pressing send. A keyboard that is composed and
    then not attached, or a filter that narrows the displayed count but not the actual fan-out,
    sends a different broadcast than the one on screen — and neither failure is visible from the
    outside.
    """
    seen: dict = {}

    class FakeRepo:
        def __init__(self, session: object) -> None:
            pass

        async def list_all_ids(self) -> list[int]:
            raise AssertionError("the panel broadcast must use the refined audience")

        async def audience_ids(self, langs=None, **kw) -> list[int]:
            seen["langs"] = langs
            seen.update(kw)
            return [21, 22]

        async def mark_unreachable(self, telegram_ids: list[int], at: object) -> int:
            return len(telegram_ids)

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

    markups: list = []

    class _KbBot:
        def __init__(self) -> None:
            self.sent: list[int] = []

        async def send_message(
            self, chat_id: int, text: str, parse_mode: str | None = None, **kw: object
        ) -> object:
            self.sent.append(chat_id)
            markups.append(kw.get("reply_markup"))
            return SimpleNamespace(chat=SimpleNamespace(id=chat_id), message_id=1)

        async def edit_message_text(self, text: str, chat_id: int = 0, message_id: int = 0) -> None:
            return None

    bot = _KbBot()
    ctx = {"bot": bot, "sessionmaker": lambda: FakeSession()}
    await broadcast_text(
        ctx,
        "hi",
        admin_id=999,
        languages=["fa"],
        only_active=True,
        only_referrers=True,
        buttons=[
            {"text": "Channel", "url": "https://t.me/gozarx"},
            {"text": "broken", "url": ""},  # dropped, rather than failing the whole send
        ],
    )

    assert seen == {"langs": [Language.fa], "only_active": True, "only_referrers": True}
    audience = [m for chat, m in zip(bot.sent, markups, strict=True) if chat != 999]
    assert audience and all(m is not None for m in audience)
    rows = audience[0].inline_keyboard
    assert [(b.text, b.url) for row in rows for b in row] == [("Channel", "https://t.me/gozarx")]
