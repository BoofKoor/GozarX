"""PendingNotifications buffer: flush sends queued actions and clears; one failure isolates."""

from __future__ import annotations

from types import SimpleNamespace

from aiogram.exceptions import TelegramBadRequest
from aiogram.methods import GetMe

from gozar.bot.notifications import PendingNotifications


def _bad_request(message: str) -> TelegramBadRequest:
    return TelegramBadRequest(method=GetMe(), message=message)


class _EditMsg:
    """A message whose first edit_text raises (as if Telegram rejected a custom-emoji button)."""

    def __init__(self, error: Exception | None = None) -> None:
        self.markups: list = []
        self._error = error

    async def edit_text(self, text: str, reply_markup=None, link_preview_options=None) -> None:
        self.markups.append(reply_markup)
        if len(self.markups) == 1 and self._error is not None:
            raise self._error


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


async def test_edit_retries_without_emoji_when_rejected() -> None:
    # A custom-emoji BadRequest on the delivered-config edit retries once with the icon-less markup,
    # so a bad premium emoji never costs the user their config.
    msg = _EditMsg(_bad_request("Bad Request: MESSAGE_CUSTOM_EMOJI_INVALID"))
    notify = PendingNotifications()
    notify.edit(msg, "cfg", reply_markup="EMOJI_KB", fallback_reply_markup="PLAIN_KB")
    await notify.flush(None)
    assert msg.markups == ["EMOJI_KB", "PLAIN_KB"]


async def test_edit_does_not_fall_back_on_unrelated_error() -> None:
    # An unrelated BadRequest must NOT swap in the fallback; it propagates and flush isolates it.
    msg = _EditMsg(_bad_request("Bad Request: message is not modified"))
    notify = PendingNotifications()
    notify.edit(msg, "cfg", reply_markup="EMOJI_KB", fallback_reply_markup="PLAIN_KB")
    await notify.flush(None)
    assert msg.markups == ["EMOJI_KB"]  # no retry


async def test_edit_emoji_error_without_fallback_just_propagates() -> None:
    # No fallback staged (ad had no emoji) -> emoji error simply propagates and is swallowed.
    msg = _EditMsg(_bad_request("Bad Request: CUSTOM_EMOJI_INVALID"))
    notify = PendingNotifications()
    notify.edit(msg, "cfg", reply_markup="EMOJI_KB")
    await notify.flush(None)
    assert msg.markups == ["EMOJI_KB"]
