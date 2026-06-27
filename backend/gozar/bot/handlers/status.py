"""Status screen: identity, referrals, daily allowance, a config-received line, usage + time left.

For an ``active_config`` user this re-reads the live panel state (which also self-heals an ended
trial), so usage/time-left are real and shown only while a trial is live.
"""

from __future__ import annotations

from aiogram import F, Router
from aiogram.types import CallbackQuery, Message

from gozar.bot import callbacks as cb
from gozar.bot.keyboards import back_keyboard, status_keyboard
from gozar.db.models.enums import Language
from gozar.db.models.user import User
from gozar.services.content import ContentService
from gozar.services.trial import PanelError, StatusInfo, TrialService
from gozar.ui.buttons import ButtonOverrides

router = Router(name="status")


async def _status_body(info: StatusInfo, content: ContentService, lang: Language) -> str:
    """The status body via content tokens: the received/not-received line + (only when active) the
    usage block. ``status_usage`` is empty when claimable, so usage/time-left are hidden."""
    line = await content.text("status_received" if info.active else "status_not_received", lang)
    usage = (
        await content.text("status_usage", lang, usage=info.usage, remaining=info.remaining)
        if info.active
        else ""
    )
    return await content.text(
        "status",
        lang,
        tg_id=info.tg_id,
        referrals=info.referrals,
        daily_limit=info.daily_limit,
        configs=info.configs,
        status_line=line,
        status_usage=usage,
    )


@router.callback_query(F.data == cb.MENU_STATUS)
async def show_status(
    callback: CallbackQuery,
    user: User,
    content: ContentService,
    trial: TrialService,
    buttons: ButtonOverrides,
) -> None:
    await callback.answer()
    info = await trial.status(user)
    lang = user.language
    if isinstance(info, PanelError):
        text = await content.text("panel_error", lang)
        markup = back_keyboard(lang, buttons)
    else:
        text = await _status_body(info, content, lang)
        markup = status_keyboard(lang, active=info.active, buttons=buttons)
    if isinstance(callback.message, Message):
        await callback.message.edit_text(text, reply_markup=markup)
