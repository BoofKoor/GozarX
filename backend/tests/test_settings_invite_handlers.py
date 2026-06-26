"""Settings + invite: the reminder toggle flips the flag; keyboards + deep link build correctly.

Stub events + fakeredis-backed content (no DB) — the callback ``edit_text`` path is guarded by an
``isinstance(.., Message)`` check, so these assert the state change + the pure builders.
"""

from __future__ import annotations

from types import SimpleNamespace

import fakeredis.aioredis

from gozar.bot import callbacks as cb
from gozar.bot.handlers.invite import invite_link
from gozar.bot.handlers.settings import toggle_reminder
from gozar.bot.keyboards import invite_keyboard, settings_keyboard
from gozar.db.models.enums import Language
from gozar.db.models.user import User
from gozar.services.content import ContentService


async def _content(**entries: str) -> ContentService:
    redis = fakeredis.aioredis.FakeRedis(decode_responses=True)
    for key, body in entries.items():
        await redis.set(key, body)
    return ContentService(None, redis)  # type: ignore[arg-type]  # session unused on a cache hit


async def test_toggle_reminder_flips_flag() -> None:
    content = await _content(**{"cache:content:fa:settings_menu": "تنظیمات"})
    user = User(telegram_id=10, language=Language.fa, reminder_enabled=True)
    answered: dict = {}

    async def answer(text: str | None = None, **kw: object) -> None:
        answered["text"] = text

    callback = SimpleNamespace(answer=answer, message=None)
    await toggle_reminder(callback, user, content)
    assert user.reminder_enabled is False
    assert answered["text"]  # a confirmation toast was shown

    await toggle_reminder(callback, user, content)
    assert user.reminder_enabled is True


def test_settings_keyboard_reflects_state() -> None:
    on = settings_keyboard(Language.en, reminder_enabled=True)
    buttons = [b for row in on.inline_keyboard for b in row]
    datas = [b.callback_data for b in buttons]
    assert cb.SETTINGS_LANG in datas
    assert cb.SETTINGS_REMINDER_TOGGLE in datas
    assert cb.MENU_HOME in datas
    toggle = next(b for b in buttons if b.callback_data == cb.SETTINGS_REMINDER_TOGGLE)
    assert "✅" in toggle.text  # enabled -> check mark

    off = settings_keyboard(Language.en, reminder_enabled=False)
    toggle_off = next(
        b
        for row in off.inline_keyboard
        for b in row
        if b.callback_data == cb.SETTINGS_REMINDER_TOGGLE
    )
    assert "❌" in toggle_off.text  # disabled -> cross mark


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
