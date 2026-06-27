"""Admin keyboard structure + namespaced callback data."""

from __future__ import annotations

from aiogram.types import InlineKeyboardMarkup

from gozar.bot import callbacks as cb
from gozar.bot.keyboards import (
    admin_back_keyboard,
    admin_menu_keyboard,
    admin_user_card_keyboard,
    confirm_keyboard,
)
from gozar.db.models.enums import Language


def _callbacks(markup: InlineKeyboardMarkup) -> list[str]:
    return [btn.callback_data for row in markup.inline_keyboard for btn in row]


def test_admin_menu_keyboard() -> None:
    assert _callbacks(admin_menu_keyboard(Language.fa)) == [
        cb.ADMIN_STATS,
        cb.ADMIN_USERS,
        cb.ADMIN_BROADCAST,
        cb.ADMIN_FORWARD,
        cb.ADMIN_REFRESH_LOCATIONS,
        cb.ADMIN_RESET_ALL,
        cb.ADMIN_CLOSE,
    ]


def test_admin_back_keyboard() -> None:
    assert _callbacks(admin_back_keyboard(Language.en)) == [cb.ADMIN_MENU]


def test_user_card_active_offers_ban() -> None:
    assert _callbacks(admin_user_card_keyboard(Language.en, banned=False)) == [
        cb.ADMIN_USER_BAN,
        cb.ADMIN_USER_RECLAIM,
        cb.ADMIN_USER_ZERO_REFERRALS,
        cb.ADMIN_MENU,
    ]


def test_user_card_banned_offers_unban() -> None:
    assert _callbacks(admin_user_card_keyboard(Language.en, banned=True)) == [
        cb.ADMIN_USER_UNBAN,
        cb.ADMIN_USER_RECLAIM,
        cb.ADMIN_USER_ZERO_REFERRALS,
        cb.ADMIN_MENU,
    ]


def test_confirm_keyboard_carries_its_pair() -> None:
    kb = confirm_keyboard(
        Language.en, cb.ADMIN_SEND_CONFIRM, cb.ADMIN_SEND_CANCEL, confirm_key="admin_send"
    )
    assert _callbacks(kb) == [cb.ADMIN_SEND_CONFIRM, cb.ADMIN_SEND_CANCEL]
