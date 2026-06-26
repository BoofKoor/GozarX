"""Today's-config flow: provision -> location picker -> deliver -> change location.

``menu:config`` provisions a fresh trial (or recognises a live one) and shows the picker built from
that subscription. A ``config:claim:{i}`` pick is the FIRST delivery — it writes one ``config_log``
row. ``config:change`` re-opens the picker and ``config:loc:{i}`` re-delivers WITHOUT logging (it is
a change, not a new claim). Links contain ``&``/``#``/``<`` so the link + location are HTML-escaped.
"""

from __future__ import annotations

import html

from aiogram import F, Router
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, Message

from gozar.bot import callbacks as cb
from gozar.bot.keyboards import (
    back_keyboard,
    config_delivered_keyboard,
    location_keyboard,
)
from gozar.db.models.user import User
from gozar.db.repositories.config_log import ConfigLogRepository
from gozar.services.content import ContentService
from gozar.services.trial import (
    AlreadyActive,
    AlreadyClaimedToday,
    ClaimResult,
    NoLocations,
    NotReady,
    PanelError,
    Provisioned,
    TrialService,
)

router = Router(name="config")


async def _edit(callback: CallbackQuery, text: str, markup: InlineKeyboardMarkup) -> None:
    if isinstance(callback.message, Message):
        await callback.message.edit_text(text, reply_markup=markup)


def _parse_index(raw: str) -> int | None:
    try:
        return int(raw)
    except ValueError:
        return None


async def _render_claim(
    result: ClaimResult, user: User, content: ContentService
) -> tuple[str, InlineKeyboardMarkup]:
    lang = user.language
    if isinstance(result, Provisioned):
        text = await content.text("config_size", lang, size=result.size)
        return text, location_keyboard(result.remarks, cb.CONFIG_CLAIM_PREFIX, lang)
    if isinstance(result, AlreadyActive):
        # Already holding a live trial — re-deliveries are changes (CONFIG_LOC, no new log).
        text = await content.text("choose_location", lang)
        return text, location_keyboard(result.remarks, cb.CONFIG_LOC_PREFIX, lang)
    key = {
        AlreadyClaimedToday: "already_claimed",
        NotReady: "not_ready",
        NoLocations: "no_locations",
        PanelError: "panel_error",
    }[type(result)]
    return await content.text(key, lang), back_keyboard(lang)


@router.callback_query(F.data == cb.MENU_CONFIG)
async def open_config(
    callback: CallbackQuery, user: User, content: ContentService, trial: TrialService
) -> None:
    await callback.answer()
    result = await trial.claim(user)
    text, markup = await _render_claim(result, user, content)
    await _edit(callback, text, markup)


async def _deliver(
    callback: CallbackQuery,
    user: User,
    content: ContentService,
    trial: TrialService,
    prefix: str,
    log_repo: ConfigLogRepository | None,
) -> None:
    await callback.answer()
    index = _parse_index((callback.data or "").removeprefix(prefix))
    if index is None:
        return
    delivery = await trial.link_for(user, index)
    if delivery is None:  # trial just ended / cache lost — nudge them to claim again
        text = await content.text("panel_error", user.language)
        await _edit(callback, text, back_keyboard(user.language))
        return
    if log_repo is not None:
        await log_repo.add(user.telegram_id, delivery.location)
    text = await content.text(
        "config_delivered",
        user.language,
        location=html.escape(delivery.location),
        link=html.escape(delivery.link),
        expires=delivery.expires,
    )
    await _edit(callback, text, config_delivered_keyboard(user.language))


@router.callback_query(F.data.startswith(cb.CONFIG_CLAIM_PREFIX))
async def deliver_claim(
    callback: CallbackQuery,
    user: User,
    content: ContentService,
    trial: TrialService,
    config_log_repo: ConfigLogRepository,
) -> None:
    await _deliver(callback, user, content, trial, cb.CONFIG_CLAIM_PREFIX, config_log_repo)


@router.callback_query(F.data.startswith(cb.CONFIG_LOC_PREFIX))
async def deliver_change(
    callback: CallbackQuery, user: User, content: ContentService, trial: TrialService
) -> None:
    await _deliver(callback, user, content, trial, cb.CONFIG_LOC_PREFIX, log_repo=None)


@router.callback_query(F.data == cb.CONFIG_CHANGE)
async def change_location(
    callback: CallbackQuery, user: User, content: ContentService, trial: TrialService
) -> None:
    await callback.answer()
    result = await trial.locations(user)
    lang = user.language
    if isinstance(result, PanelError):
        await _edit(callback, await content.text("panel_error", lang), back_keyboard(lang))
        return
    if not result:  # nothing live to change
        await _edit(callback, await content.text("no_locations", lang), back_keyboard(lang))
        return
    text = await content.text("choose_location", lang)
    await _edit(callback, text, location_keyboard(result, cb.CONFIG_LOC_PREFIX, lang))
