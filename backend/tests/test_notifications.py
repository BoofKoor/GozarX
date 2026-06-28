"""PendingNotifications buffer: flush sends queued actions and clears; one failure isolates."""

from __future__ import annotations

from types import SimpleNamespace

from gozar.bot.notifications import PendingNotifications


class _Bot:
    def __init__(self, fail_chat: int | None = None) -> None:
        self.sent: list[tuple[int, str]] = []
        self._fail_chat = fail_chat

    async def send_message(
        self, chat_id: int, text: str, reply_markup=None, link_preview_options=None
    ) -> None:
        if chat_id == self._fail_chat:
            raise RuntimeError("blocked")
        self.sent.append((chat_id, text))


async def test_flush_sends_then_clears() -> None:
    notify = PendingNotifications()
    notify.send(1, "a")
    notify.send(2, "b")
    bot = _Bot()
    await notify.flush(bot)
    assert bot.sent == [(1, "a"), (2, "b")]
    await notify.flush(bot)  # buffer cleared — no resend
    assert bot.sent == [(1, "a"), (2, "b")]


async def test_one_failure_does_not_block_others() -> None:
    notify = PendingNotifications()
    notify.send(1, "a")
    notify.send(2, "boom")  # chat 2 raises
    notify.send(3, "c")
    bot = _Bot(fail_chat=2)
    await notify.flush(bot)
    assert bot.sent == [(1, "a"), (3, "c")]  # 2 failed; 1 + 3 still delivered


async def test_send_is_noop_without_bot() -> None:
    notify = PendingNotifications()
    notify.send(1, "a")
    await notify.flush(None)  # bot disabled (dev) — nothing sent, no error


async def test_edit_uses_message_bound_bot() -> None:
    edited: dict = {}

    async def edit_text(text: str, reply_markup=None, link_preview_options=None) -> None:
        edited["text"] = text

    notify = PendingNotifications()
    notify.edit(SimpleNamespace(edit_text=edit_text), "hello")
    await notify.flush(None)  # edit doesn't need the bot arg
    assert edited["text"] == "hello"
