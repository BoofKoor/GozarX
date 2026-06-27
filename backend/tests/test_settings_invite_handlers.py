"""Settings reminder sub-screen handlers + invite deep link / keyboard.

Stub events + fakeredis-backed content (no DB) — the callback ``edit_text`` path is guarded by an
``isinstance(.., Message)`` check, so these assert the state change + the pure builders.
"""

from __future__ import annotations

from types import SimpleNamespace

import fakeredis.aioredis

from gozar.bot import callbacks as cb
from gozar.bot.handlers.invite import invite_link
from gozar.bot.handlers.settings import reminder_settings, set_reminder_off, set_reminder_on
from gozar.bot.keyboards import invite_keyboard
from gozar.db.models.enums import Language
from gozar.db.models.user import User
from gozar.services.content import ContentService


async def _content(**entries: str) -> ContentService:
    redis = fakeredis.aioredis.FakeRedis(decode_responses=True)
    for key, body in entries.items():
        await redis.set(key, body)
    return ContentService(None, redis)  # type: ignore[arg-type]  # session unused on a cache hit


def _callback() -> SimpleNamespace:
    async def answer(text: str | None = None, **kw: object) -> None:
        return None

    return SimpleNamespace(answer=answer, message=None)


async def test_reminder_sub_screen_handlers_flip_flag() -> None:
    content = await _content(
        **{
            "cache:content:fa:reminder_setting": "set",
            "cache:content:fa:reminder_status": "updated",
        }
    )
    user = User(telegram_id=10, language=Language.fa, reminder_enabled=True)
    callback = _callback()

    await set_reminder_off(callback, user, content)
    assert user.reminder_enabled is False
    await set_reminder_on(callback, user, content)
    assert user.reminder_enabled is True
    await reminder_settings(callback, user, content)  # opening the sub-screen doesn't change state
    assert user.reminder_enabled is True


def test_invite_link_format() -> None:
    assert invite_link("MyBot", 12345) == "https://t.me/MyBot?start=12345"
    assert invite_link("", 7) == "—"  # not configured -> placeholder, not a broken URL


def test_invite_keyboard_has_share_and_back() -> None:
    kb = invite_keyboard(Language.en, "https://t.me/MyBot?start=12345")
    buttons = [b for row in kb.inline_keyboard for b in row]
    share = next(b for b in buttons if b.url)
    assert "t.me/share/url" in share.url
    assert "12345" in share.url  # the deep link is embedded in the share URL
    assert any(b.callback_data == cb.MENU_HOME for b in buttons)


def test_invite_keyboard_omits_share_without_real_link() -> None:
    kb = invite_keyboard(Language.en, "—")
    buttons = [b for row in kb.inline_keyboard for b in row]
    assert all(b.url is None for b in buttons)  # no share button for a placeholder link
    assert any(b.callback_data == cb.MENU_HOME for b in buttons)
