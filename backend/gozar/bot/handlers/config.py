"""Today's-config flow: landing -> provision -> picker -> deliver -> change location.

``menu:config`` renders the LANDING (no panel call): claimable -> allowance body + a get-config
button; active -> usage body + a change button. The inner ``config:claim`` button is the only place
that provisions (``claim()``) and shows the picker. A ``config:claim:{i}`` pick is the first
delivery (writes one ``config_log`` row); ``config:change`` re-opens the picker and
``config:change:{i}`` re-delivers WITHOUT logging. Links are HTML-escaped (they hold ``&``/``#``).
"""

from __future__ import annotations

import html

from aiogram import F, Router
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, Message

from gozar.bot import callbacks as cb
from gozar.bot.keyboards import (
    back_keyboard,
    config_delivered_keyboard,
    landing_keyboard,
    location_keyboard,
)
from gozar.bot.notifications import PendingNotifications
from gozar.db.models.user import User
from gozar.db.repositories.config_log import ConfigLogRepository
from gozar.services.content import ContentService
from gozar.services.referral import ReferralService
from gozar.services.trial import (
    AlreadyActive,
    AlreadyClaimedToday,
    ClaimResult,
    NoLocations,
    NotReady,
    PanelError,
    Provisioned,
    TrialService,
    human_bytes,
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
        text = await content.text("choose_location", lang)
        return text, location_keyboard(result.remarks, cb.CONFIG_CLAIM_PREFIX, lang)
    if isinstance(result, AlreadyActive):
        # Already holding a live trial — re-deliveries are changes (CONFIG_CHANGE, no new log).
        text = await content.text("choose_location", lang)
        return text, location_keyboard(result.remarks, cb.CONFIG_CHANGE_PREFIX, lang)
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
    """The get-config LANDING — renders the user's current state and creates NO panel user."""
    await callback.answer()
    info = await trial.status(user)  # no panel call when claimable; self-heals an expired trial
    lang = user.language
    if isinstance(info, PanelError):
        await _edit(callback, await content.text("panel_error", lang), back_keyboard(lang))
        return
    if info.active:
        text = await content.text(
            "config_active",
            lang,
            remaining=info.remaining,
            usage=info.usage,
            total=info.daily_limit,
        )
    else:
        text = await content.text("config_size", lang, size=info.daily_limit)
    await _edit(callback, text, landing_keyboard(lang, active=info.active))


@router.callback_query(F.data == cb.CONFIG_CLAIM)
async def start_claim(
    callback: CallbackQuery, user: User, content: ContentService, trial: TrialService
) -> None:
    """The landing's inner get-config button — the ONLY place that provisions, then the picker."""
    await callback.answer()
    result = await trial.claim(user)
    text, markup = await _render_claim(result, user, content)
    await _edit(callback, text, markup)


async def _maybe_award_referral(
    invitee: User,
    content: ContentService,
    log_repo: ConfigLogRepository,
    referral: ReferralService,
    notify: PendingNotifications,
) -> None:
    """On the invitee's FIRST delivered config (count just became 1), credit their referrer and
    queue the inviter's notice — SENT post-commit so the +1 is durable first."""
    if not invitee.referred_by:
        return
    if await log_repo.count_for_user(invitee.telegram_id) != 1:
        return
    award = await referral.award_first_claim(invitee)
    if award is None:
        return
    text = await content.text(
        "referral_joined",
        award.inviter.language,
        count=award.new_count,
        size=human_bytes(award.new_daily_bytes),
    )
    notify.send(award.inviter.telegram_id, text)


async def _deliver(
    callback: CallbackQuery,
    user: User,
    content: ContentService,
    trial: TrialService,
    notify: PendingNotifications,
    prefix: str,
    log_repo: ConfigLogRepository | None,
    referral: ReferralService | None,
) -> None:
    # DB work only; every user-facing send is QUEUED on `notify` and flushed by the middleware AFTER
    # the commit (so the invitee's config + the inviter's referral notice never precede the write).
    await callback.answer()
    message = callback.message
    if not isinstance(message, Message):
        return
    index = _parse_index((callback.data or "").removeprefix(prefix))
    if index is None:
        return
    delivery = await trial.link_for(user, index)
    if delivery is None:  # trial just ended / cache lost — nudge them to claim again
        text = await content.text("panel_error", user.language)
        notify.edit(message, text, back_keyboard(user.language))
        return
    if log_repo is not None:  # claim path — write the one log row, then maybe credit the referrer
        await log_repo.add(user.telegram_id, delivery.location)
        if referral is not None:
            await _maybe_award_referral(user, content, log_repo, referral, notify)
    text = await content.text(
        "config_delivered",
        user.language,
        location=html.escape(delivery.location),
        link=html.escape(delivery.link),
        expires=delivery.expires,
    )
    notify.edit(message, text, config_delivered_keyboard(user.language))


@router.callback_query(F.data.startswith(cb.CONFIG_CLAIM_PREFIX))
async def deliver_claim(
    callback: CallbackQuery,
    user: User,
    content: ContentService,
    trial: TrialService,
    notify: PendingNotifications,
    config_log_repo: ConfigLogRepository,
    referral: ReferralService,
) -> None:
    await _deliver(
        callback, user, content, trial, notify, cb.CONFIG_CLAIM_PREFIX, config_log_repo, referral
    )


@router.callback_query(F.data.startswith(cb.CONFIG_CHANGE_PREFIX))
async def deliver_change(
    callback: CallbackQuery,
    user: User,
    content: ContentService,
    trial: TrialService,
    notify: PendingNotifications,
) -> None:
    await _deliver(
        callback,
        user,
        content,
        trial,
        notify,
        cb.CONFIG_CHANGE_PREFIX,
        log_repo=None,
        referral=None,
    )


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
    await _edit(callback, text, location_keyboard(result, cb.CONFIG_CHANGE_PREFIX, lang))


@router.callback_query(F.data.startswith(cb.LOC_PAGE_PREFIX))
async def paginate_locations(
    callback: CallbackQuery, user: User, content: ContentService, trial: TrialService
) -> None:
    """Re-render the picker at another page — a pure view change (no claim/log/referral logic).

    The ``{tag}`` in ``loc:page:{tag}:{N}`` preserves the delivery prefix (claim vs change), so a
    paginated first-claim picker still delivers via ``config:claim:`` and writes its one log row.
    """
    await callback.answer()
    tag, _, page_str = (callback.data or "").removeprefix(cb.LOC_PAGE_PREFIX).partition(":")
    page = _parse_index(page_str) or 0
    prefix = cb.CONFIG_CLAIM_PREFIX if tag == "claim" else cb.CONFIG_CHANGE_PREFIX
    result = await trial.locations(user)
    lang = user.language
    if isinstance(result, PanelError):
        await _edit(callback, await content.text("panel_error", lang), back_keyboard(lang))
        return
    if not result:
        await _edit(callback, await content.text("no_locations", lang), back_keyboard(lang))
        return
    text = await content.text("choose_location", lang)
    await _edit(callback, text, location_keyboard(result, prefix, lang, page=page))
