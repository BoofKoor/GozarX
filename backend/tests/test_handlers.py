"""Bot handlers via direct calls (stub events + fakeredis-backed content; no DB).

The ContentService reads its cache first, so pre-seeding fakeredis lets us drive handlers without a
DB or a live bot. Message ``answer`` is captured via a stub; callback ``edit_text`` is guarded by an
``isinstance(.., Message)`` check in production, so these tests assert the state changes + the
``message.answer`` path (the edit path is exercised on real events / the server).
"""

from __future__ import annotations

from types import SimpleNamespace

import fakeredis.aioredis

from gozar.bot import callbacks as cb
from gozar.bot.handlers.start import cmd_start, set_language
from gozar.db.models.enums import Language
from gozar.db.models.user import User
from gozar.services.content import ContentService
from gozar.ui.buttons import EMPTY_OVERRIDES


async def _content(**entries: str) -> ContentService:
    redis = fakeredis.aioredis.FakeRedis(decode_responses=True)
    for key, body in entries.items():
        await redis.set(key, body)
    return ContentService(None, redis)  # type: ignore[arg-type]  # session unused on a cache hit


def _message() -> tuple[SimpleNamespace, dict]:
    sent: dict = {}

    async def answer(text: str, reply_markup=None) -> None:
        sent["text"] = text
        sent["markup"] = reply_markup

    return SimpleNamespace(answer=answer), sent


async def test_start_new_user_shows_language_picker() -> None:
    content = await _content(**{"cache:content:fa:choose_language": "زبان؟"})
    user = User(telegram_id=10, language=Language.fa)
    message, sent = _message()
    await cmd_start(
        message,
        SimpleNamespace(args=None),
        user,
        created=True,
        content=content,
        buttons=EMPTY_OVERRIDES,
    )
    assert sent["text"] == "زبان؟"
    callbacks = [b.callback_data for row in sent["markup"].inline_keyboard for b in row]
    assert callbacks == ["lang:set:fa", "lang:set:en", "lang:set:ru"]


async def test_start_records_referrer_and_ignores_self() -> None:
    content = await _content(**{"cache:content:fa:choose_language": "x"})
    message, _ = _message()

    user = User(telegram_id=10, language=Language.fa)
    await cmd_start(
        message,
        SimpleNamespace(args="555"),
        user,
        created=True,
        content=content,
        buttons=EMPTY_OVERRIDES,
    )
    assert user.referred_by == 555

    self_ref = User(telegram_id=10, language=Language.fa)
    await cmd_start(
        message,
        SimpleNamespace(args="10"),
        self_ref,
        created=True,
        content=content,
        buttons=EMPTY_OVERRIDES,
    )
    assert self_ref.referred_by is None


async def test_start_existing_user_shows_menu() -> None:
    content = await _content(**{"cache:content:fa:main_menu": "منو"})
    user = User(telegram_id=10, language=Language.fa)
    message, sent = _message()
    await cmd_start(
        message,
        SimpleNamespace(args=None),
        user,
        created=False,
        content=content,
        buttons=EMPTY_OVERRIDES,
    )
    assert sent["text"] == "منو"
    callbacks = [b.callback_data for row in sent["markup"].inline_keyboard for b in row]
    assert cb.MENU_CONFIG in callbacks


async def test_set_language_updates_language() -> None:
    content = await _content(**{"cache:content:en:welcome": "Welcome"})
    user = User(telegram_id=10, language=Language.fa)
    answered: dict = {}

    async def cb_answer(text: str | None = None, **kw: object) -> None:
        answered["called"] = True

    callback = SimpleNamespace(data=cb.lang_cb("en"), message=None, answer=cb_answer)
    await set_language(callback, user, content, buttons=EMPTY_OVERRIDES)
    assert user.language is Language.en
    assert answered["called"] is True
