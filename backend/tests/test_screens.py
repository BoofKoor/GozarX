"""The screen sender: the best rendering Telegram takes, never a failed screen because of the look,
and what Telegram's answers teach the look — plus the console's one live screen per chat."""

from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace

import fakeredis.aioredis
import pytest
from aiogram.exceptions import TelegramBadRequest
from aiogram.methods import SendMessage
from aiogram.types import (
    Chat,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
    MessageEntity,
    RichBlockParagraph,
    RichMessage,
    RichTextCustomEmoji,
)

from gozar.bot import screens
from gozar.bot.handlers.admin.console import Console
from gozar.db.models.enums import Language
from gozar.services.look import LookService
from gozar.ui.look import PLAIN, Look
from gozar.ui.rich import Btn, Doc


def _bad(text: str) -> TelegramBadRequest:
    return TelegramBadRequest(method=SendMessage(chat_id=1, text="x"), message=text)


class FakeLooks:
    def __init__(self) -> None:
        self.refusals: list[str] = []
        self.kepts = 0

    async def refused(self, reason: str) -> None:
        self.refusals.append(reason)

    async def kept(self) -> None:
        self.kepts += 1


class FakeBot:
    """Plays Telegram: ``refuse`` decides which calls fail (by kind and whether they carry custom
    emoji); ``drop_emoji`` plays a bot owner without Premium (custom emoji silently removed)."""

    def __init__(self, refuse=None, drop_emoji: bool = False, uneditable: bool = False) -> None:
        self.calls: list[tuple[str, str, object]] = []
        self.deleted: list[int] = []
        self._refuse = refuse or (lambda kind, body: None)
        self._drop = drop_emoji
        self._uneditable = uneditable
        self._next = 1000

    def _message(self, body: str, rich: bool) -> Message:
        """A real aiogram Message, as Telegram answers: custom emoji kept unless ``drop_emoji``."""
        self._next += 1
        emoji = "tg-emoji" in body and not self._drop
        common = {
            "message_id": self._next,
            "date": datetime.now(UTC),
            "chat": Chat(id=1, type="private"),
        }
        if rich:
            blocks = (
                [
                    RichBlockParagraph(
                        text=RichTextCustomEmoji(custom_emoji_id="1", alternative_text="🏠")
                    )
                ]
                if emoji
                else []
            )
            return Message(**common, rich_message=RichMessage(blocks=blocks))
        entities = (
            [MessageEntity(type="custom_emoji", offset=0, length=2, custom_emoji_id="1")]
            if emoji
            else []
        )
        return Message(**common, text=body, entities=entities)

    def _check(self, kind: str, body: str) -> None:
        reason = self._refuse(kind, body)
        if reason:
            raise _bad(reason)

    async def send_rich_message(self, chat_id, rich_message, reply_markup=None):  # noqa: ANN001, ANN201
        self.calls.append(("send_rich", rich_message.html, reply_markup))
        self._check("rich", rich_message.html)
        return self._message(rich_message.html, rich=True)

    async def send_message(self, chat_id, text, reply_markup=None):  # noqa: ANN001, ANN201
        self.calls.append(("send", text, reply_markup))
        self._check("classic", text)
        return self._message(text, rich=False)

    async def edit_message_text(
        self, text=None, *, chat_id, message_id, reply_markup=None, rich_message=None, **kw
    ):  # noqa: ANN001, ANN201, E501
        body = rich_message.html if rich_message is not None else text
        kind = "rich" if rich_message is not None else "classic"
        self.calls.append((f"edit_{kind}", body, reply_markup))
        if self._uneditable:
            raise _bad("Bad Request: message to edit not found")
        self._check(kind, body)
        message = self._message(body, rich=rich_message is not None)
        return message.model_copy(update={"message_id": message_id})

    async def delete_message(self, chat_id, message_id):  # noqa: ANN001, ANN201
        self.deleted.append(message_id)
        return True


def _doc() -> Doc:
    return Doc().h("🏠 Home", 2).kv([("🔑 key", "1")]).row([Btn("📑", copy="v")])


async def test_a_rich_screen_goes_out_rich_with_premium_icons() -> None:
    bot, looks = FakeBot(), FakeLooks()
    await screens.send(bot, 1, _doc(), look=Look(), looks=looks)
    assert [c[0] for c in bot.calls] == ["send_rich"]
    assert "tg-emoji" in bot.calls[0][1]
    assert looks.kepts == 1 and looks.refusals == []  # Telegram kept them: the owner has Premium


async def test_refused_icons_fall_back_to_plain_and_are_remembered() -> None:
    bot = FakeBot(
        refuse=lambda kind, body: "Bad Request: DOCUMENT_INVALID" if "tg-emoji" in body else None
    )
    looks = FakeLooks()
    await screens.send(bot, 1, _doc(), look=Look(), looks=looks)
    assert [c[0] for c in bot.calls] == ["send_rich", "send_rich"]
    assert "tg-emoji" not in bot.calls[1][1]
    assert looks.refusals == ["Telegram server says - Bad Request: DOCUMENT_INVALID"]


async def test_dropped_custom_emoji_read_as_refused() -> None:
    # Telegram silently drops custom emoji for a bot whose owner has no Premium.
    bot, looks = FakeBot(drop_emoji=True), FakeLooks()
    await screens.send(bot, 1, "🏠 home", look=Look(), looks=looks)
    assert looks.refusals == ["Telegram dropped the custom emoji"]


async def test_no_rich_messages_falls_back_to_a_regular_one_with_the_buttons_moved() -> None:
    bot = FakeBot(refuse=lambda kind, body: "Bad Request: unsupported" if kind == "rich" else None)
    looks = FakeLooks()
    await screens.send(bot, 1, _doc(), look=Look(), looks=looks)
    assert [c[0] for c in bot.calls] == ["send_rich", "send_rich", "send"]
    markup = bot.calls[-1][2]
    assert markup.inline_keyboard[0][0].copy_text.text == "v"  # the in-text copy button survived
    assert looks.refusals == []  # rich failed with AND without icons: the icons were not why


async def test_a_plain_look_sends_one_regular_message() -> None:
    bot = FakeBot()
    await screens.send(bot, 1, _doc(), look=PLAIN)
    assert [c[0] for c in bot.calls] == ["send"]
    assert "tg-emoji" not in bot.calls[0][1]


async def test_a_real_problem_still_raises() -> None:
    bot = FakeBot(refuse=lambda kind, body: "Bad Request: chat not found")
    with pytest.raises(TelegramBadRequest):
        await screens.send(bot, 1, "hi", look=PLAIN)


async def test_not_modified_is_not_an_error() -> None:
    bot = FakeBot(refuse=lambda kind, body: "Bad Request: message is not modified")
    assert await screens.edit(bot, 1, 7, _doc(), look=Look()) is None
    assert len(bot.calls) == 1 and bot.deleted == []


async def test_an_uneditable_message_is_replaced_by_a_new_one() -> None:
    bot = FakeBot(uneditable=True)
    shown = await screens.edit(bot, 1, 7, _doc(), look=Look())
    assert [c[0] for c in bot.calls] == ["edit_rich", "send_rich"]  # no other rendering tried
    assert shown.message_id != 7 and bot.deleted == [7]


async def test_the_console_keeps_one_live_screen() -> None:
    redis = fakeredis.aioredis.FakeRedis(decode_responses=True)
    store = screens.ScreenStore(redis)
    bot = FakeBot()
    console = Console(bot, 5, Language.en, PLAIN, LookService(None, redis), store)

    first = await console.show("one", new=True)
    assert await store.get(5) == first.message_id
    await console.show("two")  # a typed answer: the live screen is edited
    assert bot.calls[-1][0] == "edit_classic" and await store.get(5) == first.message_id

    button_on_old = SimpleNamespace(message_id=55)
    await console.show("three", at=button_on_old)  # not a Message: treated as no anchor
    second = await console.show("four", new=True)  # /admin again: fresh screen, old one deleted
    assert first.message_id in bot.deleted
    assert await store.get(5) == second.message_id
    await console.close()
    assert second.message_id in bot.deleted and await store.get(5) is None


def test_variants_are_tried_best_first() -> None:
    markup = InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text="🗑 Delete", callback_data="x:y")]]
    )
    kinds = [(v.rich, v.themed) for v in screens.variants(_doc(), markup, Look())]
    assert kinds == [(True, True), (True, False), (False, True), (False, False)]
    kinds = [(v.rich, v.themed) for v in screens.variants(_doc(), markup, Look(rich=False))]
    assert kinds == [(False, True), (False, False)]
    assert [(v.rich, v.themed) for v in screens.variants("plain", None, Look())] == [(False, False)]


async def test_icons_are_blamed_only_for_the_rendering_they_broke() -> None:
    # The rich message failed with and without icons (rich itself is the problem); the regular
    # message then went through plain — nothing says the icons were refused.
    rich_themed = screens._Variant(True, "<p>x</p>", None, True, 1)
    rich_plain = screens._Variant(True, "<p>x</p>", None, False, 0)
    classic_plain = screens._Variant(False, "x", None, False, 0)
    looks = FakeLooks()
    failed = [(rich_themed, "no rich"), (rich_plain, "no rich")]
    await screens._refused_icons(looks, failed, classic_plain)
    assert looks.refusals == []
    await screens._refused_icons(looks, [(rich_themed, "bad emoji")], rich_plain)
    assert looks.refusals == ["bad emoji"]
