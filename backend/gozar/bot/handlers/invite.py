"""Invite screen: the user's referral deep link + invite count + current daily allowance.

The deep link is ``t.me/<bot>?start=<telegram_id>``; start.py reads the ``start`` payload as the
referrer id, so a friend who opens it is recorded as ``referred_by`` (Phase 4) and credited on their
first claim (Phase 5).
"""

from __future__ import annotations

from aiogram import F, Router
from aiogram.types import CallbackQuery, Message

from gozar.bot import callbacks as cb
from gozar.bot.keyboards import invite_keyboard
from gozar.config.settings import get_settings
from gozar.db.models.user import User
from gozar.services.content import ContentService
from gozar.services.settings_service import SettingsService
from gozar.services.trial import compute_traffic_bytes, human_bytes

router = Router(name="invite")


def invite_link(bot_username: str, telegram_id: int) -> str:
    """The referral deep link. Empty username (dev / not configured) yields a placeholder, not a
    broken URL — the keyboard then omits the Share button."""
    return f"https://t.me/{bot_username}?start={telegram_id}" if bot_username else "—"


@router.callback_query(F.data == cb.MENU_INVITE)
async def open_invite(
    callback: CallbackQuery, user: User, content: ContentService, settings: SettingsService
) -> None:
    await callback.answer()
    link = invite_link(get_settings().bot_username, user.telegram_id)
    daily_size = human_bytes(await compute_traffic_bytes(settings, user.referral_count))
    text = await content.text(
        "invite", user.language, link=link, count=user.referral_count, daily_size=daily_size
    )
    if isinstance(callback.message, Message):
        await callback.message.edit_text(text, reply_markup=invite_keyboard(user.language, link))
