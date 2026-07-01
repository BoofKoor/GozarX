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
from gozar.services.settings_service import SettingKey, SettingsService
from gozar.services.trial import (
    AlreadyActive,
    AlreadyClaimedToday,
    ClaimResult,
    NoLocations,
    NotReady,
    PanelError,
    Provisioned,
    TrialService,
    compute_traffic_bytes,
    human_bytes,
)
from gozar.ui.buttons import ButtonOverrides

router = Router(name="config")


async def _edit(callback: CallbackQuery, text: str, markup: InlineKeyboardMarkup) -> None:
    if isinstance(callback.message, Message):
        await callback.message.edit_text(text, reply_markup=markup)


def _parse_index(raw: str) -> int | None:
    try:
        return int(raw)
    except ValueError:
        return None


async def _per_page(settings: SettingsService) -> int:
    return await settings.get_int(SettingKey.CONFIGS_PER_PAGE, 8)


async def _render_claim(
    result: ClaimResult,
    user: User,
    content: ContentService,
    buttons: ButtonOverrides,
    page_size: int,
) -> tuple[str, InlineKeyboardMarkup]:
    lang = user.language
    if isinstance(result, Provisioned):
        text = await content.text("choose_location", lang)
        return text, location_keyboard(
            result.remarks, cb.CONFIG_CLAIM_PREFIX, lang, page_size=page_size, buttons=buttons
        )
    if isinstance(result, AlreadyActive):
        # Already holding a live trial — re-deliveries are changes (CONFIG_CHANGE, no new log).
        text = await content.text("choose_location", lang)
        return text, location_keyboard(
            result.remarks, cb.CONFIG_CHANGE_PREFIX, lang, page_size=page_size, buttons=buttons
        )
    if isinstance(result, AlreadyClaimedToday):
        # Cooldown still running — tell them how long is left ("—" when it can't be derived).
        text = await content.text("already_claimed", lang, retry_after=result.retry_after or "—")
        return text, back_keyboard(lang, buttons)
    key = {
        NotReady: "not_ready",
        NoLocations: "no_locations",
        PanelError: "panel_error",
    }[type(result)]
    return await content.text(key, lang), back_keyboard(lang, buttons)


@router.callback_query(F.data == cb.MENU_CONFIG)
async def open_config(
    callback: CallbackQuery,
    user: User,
    content: ContentService,
    trial: TrialService,
    buttons: ButtonOverrides,
) -> None:
    """The get-config LANDING — renders the user's current state and creates NO panel user."""
    await callback.answer()
    info = await trial.status(user)  # no panel call when claimable; self-heals an expired trial
    lang = user.language
    if isinstance(info, PanelError):
        await _edit(callback, await content.text("panel_error", lang), back_keyboard(lang, buttons))
        return
    if info.active:
        # Data spent but time still valid -> 'invite to revive' copy; else the healthy-active copy.
        key = "config_limited" if info.data_exhausted else "config_active"
        text = await content.text(
            key,
            lang,
            remaining=info.remaining,
            usage=info.usage,
            total=info.daily_limit,
        )
    else:
        text = await content.text("config_size", lang, size=info.daily_limit)
    await _edit(callback, text, landing_keyboard(lang, active=info.active, buttons=buttons))


@router.callback_query(F.data == cb.CONFIG_CLAIM)
async def start_claim(
    callback: CallbackQuery,
    user: User,
    content: ContentService,
    trial: TrialService,
    settings: SettingsService,
    buttons: ButtonOverrides,
) -> None:
    """The landing's inner get-config button — the ONLY place that provisions, then the picker."""
    await callback.answer()
    result = await trial.claim(user)
    text, markup = await _render_claim(result, user, content, buttons, await _per_page(settings))
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
    msg = await content.message(
        "referral_joined",
        award.inviter.language,
        count=award.new_count,
        size=human_bytes(award.new_daily_bytes),
    )
    notify.send(award.inviter.telegram_id, msg.text, link_preview=msg.link_preview)


async def _maybe_queue_ads(
    settings: SettingsService, content: ContentService, notify: PendingNotifications, user: User
) -> None:
    """v1's 'deliver, then ads': when ads_enabled, queue the ads copy as a SEPARATE message on the
    same post-commit buffer (so it never fires on a rollback). Default off."""
    if await settings.get_bool(SettingKey.ADS_ENABLED):
        ad = await content.message("ads", user.language)
        notify.send(user.telegram_id, ad.text, link_preview=ad.link_preview)


async def _deliver(
    callback: CallbackQuery,
    user: User,
    content: ContentService,
    trial: TrialService,
    notify: PendingNotifications,
    settings: SettingsService,
    prefix: str,
    log_repo: ConfigLogRepository | None,
    referral: ReferralService | None,
    buttons: ButtonOverrides,
) -> None:
    # DB work only; every user-facing send is QUEUED on `notify` and flushed by the middleware AFTER
    # the commit (so the invitee's config + the inviter's referral notice never precede the write).
    message = callback.message
    if not isinstance(message, Message):
        await callback.answer()
        return
    index = _parse_index((callback.data or "").removeprefix(prefix))
    if index is None:
        await callback.answer()
        return
    delivery = await trial.link_for(user, index)
    if delivery is None:  # trial just ended / cache lost — nudge them to claim again
        await callback.answer()
        text = await content.text("panel_error", user.language)
        notify.edit(message, text, back_keyboard(user.language, buttons))
        return
    if log_repo is not None:  # claim path — write the one log row, then maybe credit the referrer
        await log_repo.add(user.telegram_id, delivery.location)
        if referral is not None:
            await _maybe_award_referral(user, content, log_repo, referral, notify)
        # confirm the new config with a toast at the top of the chat (claim path only, not a change)
        await callback.answer(await content.text("config_created_toast", user.language))
    else:
        await callback.answer()
    # Global state tokens so an admin can drop {total_traffic}/{remaining}/{expire} into the
    # delivered text. Total is the user's daily allowance (computed locally — no panel call; the hot
    # path stays DB-only). Live usage needs a panel call, so {used_traffic} shows "—" here (real
    # usage lives on the status screen). {expires}/{remaining}/{expire} = time-left.
    total = human_bytes(await compute_traffic_bytes(settings, user.referral_count))
    msg = await content.message(
        "config_delivered",
        user.language,
        location=html.escape(delivery.location),
        link=html.escape(delivery.link),
        expires=delivery.expires,
        remaining=delivery.expires,
        expire=delivery.expires,
        total_traffic=total,
        total=total,
        daily_limit=total,
        used_traffic="—",
        usage="—",
    )
    notify.edit(
        message,
        msg.text,
        config_delivered_keyboard(user.language, buttons),
        link_preview=msg.link_preview,
    )
    await _maybe_queue_ads(settings, content, notify, user)  # v1: ads as a 2nd message, post-commit


@router.callback_query(F.data.startswith(cb.CONFIG_CLAIM_PREFIX))
async def deliver_claim(
    callback: CallbackQuery,
    user: User,
    content: ContentService,
    trial: TrialService,
    notify: PendingNotifications,
    settings: SettingsService,
    config_log_repo: ConfigLogRepository,
    referral: ReferralService,
    buttons: ButtonOverrides,
) -> None:
    await _deliver(
        callback,
        user,
        content,
        trial,
        notify,
        settings,
        cb.CONFIG_CLAIM_PREFIX,
        config_log_repo,
        referral,
        buttons,
    )


@router.callback_query(F.data.startswith(cb.CONFIG_CHANGE_PREFIX))
async def deliver_change(
    callback: CallbackQuery,
    user: User,
    content: ContentService,
    trial: TrialService,
    notify: PendingNotifications,
    settings: SettingsService,
    buttons: ButtonOverrides,
) -> None:
    await _deliver(
        callback,
        user,
        content,
        trial,
        notify,
        settings,
        cb.CONFIG_CHANGE_PREFIX,
        log_repo=None,
        referral=None,
        buttons=buttons,
    )


@router.callback_query(F.data == cb.CONFIG_CHANGE)
async def change_location(
    callback: CallbackQuery,
    user: User,
    content: ContentService,
    trial: TrialService,
    settings: SettingsService,
    buttons: ButtonOverrides,
) -> None:
    await callback.answer()
    result = await trial.locations(user)
    lang = user.language
    if isinstance(result, PanelError):
        await _edit(callback, await content.text("panel_error", lang), back_keyboard(lang, buttons))
        return
    if not result:  # nothing live to change
        await _edit(
            callback, await content.text("no_locations", lang), back_keyboard(lang, buttons)
        )
        return
    text = await content.text("choose_location", lang)
    markup = location_keyboard(
        result, cb.CONFIG_CHANGE_PREFIX, lang, page_size=await _per_page(settings), buttons=buttons
    )
    await _edit(callback, text, markup)


@router.callback_query(F.data.startswith(cb.LOC_PAGE_PREFIX))
async def paginate_locations(
    callback: CallbackQuery,
    user: User,
    content: ContentService,
    trial: TrialService,
    settings: SettingsService,
    buttons: ButtonOverrides,
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
        await _edit(callback, await content.text("panel_error", lang), back_keyboard(lang, buttons))
        return
    if not result:
        await _edit(
            callback, await content.text("no_locations", lang), back_keyboard(lang, buttons)
        )
        return
    text = await content.text("choose_location", lang)
    markup = location_keyboard(
        result, prefix, lang, page=page, page_size=await _per_page(settings), buttons=buttons
    )
    await _edit(callback, text, markup)
