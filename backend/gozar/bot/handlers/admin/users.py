"""👤 One user: look them up by id, see the card, act on them.

``UserActionFlow`` keeps the target id in FSM state, so the card's buttons carry no id. Destructive
actions (ban, zero referrals) confirm first. The id the admin types is deleted once read, and the
card replaces the prompt on the same screen.
"""

from __future__ import annotations

from aiogram import F, Router
from aiogram.filters import StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message
from redis.asyncio import Redis

from gozar.bot import callbacks as cb
from gozar.bot.handlers.admin.console import Console
from gozar.bot.handlers.admin.home import show_home
from gozar.bot.keyboards import admin_back_keyboard, admin_user_card_keyboard, confirm_keyboard
from gozar.db.models.enums import Language, UserStatus
from gozar.db.models.user import User
from gozar.services.admin import AdminService, ReclaimRefused, UserCard
from gozar.services.content import ContentService
from gozar.ui.buttons import ButtonOverrides
from gozar.ui.console_text import tr
from gozar.ui.flags import with_flag
from gozar.ui.fmt import ago, num, when
from gozar.ui.labels import LANGUAGE_NAMES
from gozar.ui.rich import Btn, Doc, copy, esc

router = Router(name="admin.users")


class UserActionFlow(StatesGroup):
    waiting_id = State()  # awaiting the target telegram_id
    viewing = State()  # a user card is shown (target_id in state data)
    confirming = State()  # a destructive action's confirm is shown (pending in state data)


def card_doc(card: UserCard, lang: Language, note: str | None = None) -> Doc:
    u = card.user
    doc = Doc()
    if note:
        doc.quote(note)
    # no <code> in a heading: the regular rendering makes it bold, and Telegram refuses code
    # inside bold (the copy button right under it carries the id)
    doc.h(tr("user_title", lang, id=u.telegram_id), 2)
    doc.row([Btn(tr("copy", lang), copy=str(u.telegram_id))], align="left")
    rows: list[tuple[str, str] | None] = [
        (tr("user_status", lang), tr(f"status_{u.status.value}", lang)),
        (tr("user_language", lang), esc(LANGUAGE_NAMES.get(u.language, u.language.value))),
        (tr("user_referrals", lang), num(u.referral_count, lang)),
        (tr("user_configs", lang), num(card.configs, lang)),
    ]
    if card.recent:
        last = card.recent[0]
        where = f"{esc(with_flag(last.location))} • {ago(last.created_at, lang)}"
        rows.append((tr("user_last", lang), where))
    if u.panel_username:
        handle = f"<code>{esc(u.panel_username)}</code> {copy(u.panel_username, tr('copy', lang))}"
        rows.append((tr("user_panel", lang), handle))
    rows.append((tr("user_joined", lang), when(u.created_at, lang, "d") if u.created_at else "—"))
    if u.unreachable_at is not None:
        gone = tr("user_unreachable", lang, time=ago(u.unreachable_at, lang))
        rows.append((tr("user_reach", lang), gone))
    doc.kv(rows)
    if len(card.recent) > 1:
        doc.details(
            tr("user_recent", lang),
            Doc().table(
                [tr("user_when", lang), tr("stats_location", lang)],
                [[when(log.created_at, lang), esc(with_flag(log.location))] for log in card.recent],
            ),
        )
    return doc


async def show_card(
    console: Console,
    admin: AdminService,
    content: ContentService,
    user: User,
    target_id: int,
    buttons: ButtonOverrides,
    *,
    at: object = None,
    note_key: str | None = None,
) -> None:
    lang = user.language
    card = await admin.lookup(target_id)
    if card is None:
        await console.show(
            await content.text("admin_user_not_found", lang),
            admin_back_keyboard(lang, buttons),
            at=at,
        )
        return
    note = await content.text(note_key, lang) if note_key else None
    markup = admin_user_card_keyboard(
        lang, banned=card.user.status is UserStatus.banned, buttons=buttons
    )
    await console.show(card_doc(card, lang, note), markup, at=at)


@router.callback_query(F.data == cb.ADMIN_USERS)
async def start_user_lookup(
    callback: CallbackQuery,
    user: User,
    content: ContentService,
    state: FSMContext,
    console: Console,
    buttons: ButtonOverrides,
) -> None:
    await callback.answer()
    await state.set_state(UserActionFlow.waiting_id)
    await console.show(
        await content.text("admin_user_prompt", user.language),
        admin_back_keyboard(user.language, buttons),
        at=callback.message,
    )


@router.message(StateFilter(UserActionFlow.waiting_id))
async def user_lookup(
    message: Message,
    user: User,
    content: ContentService,
    state: FSMContext,
    admin: AdminService,
    console: Console,
    buttons: ButtonOverrides,
) -> None:
    raw = (message.text or "").strip()
    await console.consume(message)
    card = await admin.lookup(int(raw)) if raw.lstrip("-").isdigit() else None
    lang = user.language
    if card is None:
        # the prompt again, with what went wrong on top (the admin can just type another id)
        doc = Doc().quote(await content.text("admin_user_not_found", lang))
        doc.text(await content.text("admin_user_prompt", lang))
        await console.show(doc, admin_back_keyboard(lang, buttons))
        return
    await state.set_state(UserActionFlow.viewing)
    await state.update_data(target_id=card.user.telegram_id)
    markup = admin_user_card_keyboard(
        lang, banned=card.user.status is UserStatus.banned, buttons=buttons
    )
    await console.show(card_doc(card, lang), markup)


async def _target(state: FSMContext) -> int | None:
    data = await state.get_data()
    target_id = data.get("target_id")
    return int(target_id) if target_id is not None else None


async def _back_home(
    callback: CallbackQuery,
    user: User,
    content: ContentService,
    state: FSMContext,
    admin: AdminService,
    console: Console,
    redis: Redis,
    buttons: ButtonOverrides,
) -> None:
    """The card's state is gone (a restart, a second /admin): back to the console home."""
    await state.clear()
    await show_home(user, content, admin, console, redis, buttons, at=callback.message)


@router.callback_query(F.data == cb.ADMIN_USER_UNBAN, StateFilter(UserActionFlow.viewing))
async def user_unban(
    callback: CallbackQuery,
    user: User,
    content: ContentService,
    state: FSMContext,
    admin: AdminService,
    console: Console,
    redis: Redis,
    buttons: ButtonOverrides,
) -> None:
    await callback.answer()
    target_id = await _target(state)
    if target_id is None:
        await _back_home(callback, user, content, state, admin, console, redis, buttons)
        return
    try:
        await admin.unban(target_id)
        note = "admin_unban_done"
    except ReclaimRefused:  # a revoke pending from the ban, and the panel still not answering
        note = "admin_reclaim_panel_down"
    await show_card(
        console, admin, content, user, target_id, buttons, at=callback.message, note_key=note
    )


@router.callback_query(F.data == cb.ADMIN_USER_RECLAIM, StateFilter(UserActionFlow.viewing))
async def user_reclaim(
    callback: CallbackQuery,
    user: User,
    content: ContentService,
    state: FSMContext,
    admin: AdminService,
    console: Console,
    redis: Redis,
    buttons: ButtonOverrides,
) -> None:
    await callback.answer()
    target_id = await _target(state)
    if target_id is None:
        await _back_home(callback, user, content, state, admin, console, redis, buttons)
        return
    note = "admin_reclaim_done"
    try:
        await admin.reclaim(target_id)
    except ReclaimRefused as refused:
        note = "admin_reclaim_banned" if refused.reason == "banned" else "admin_reclaim_panel_down"
    await show_card(
        console, admin, content, user, target_id, buttons, at=callback.message, note_key=note
    )


async def _confirm(
    callback: CallbackQuery,
    user: User,
    content: ContentService,
    state: FSMContext,
    console: Console,
    buttons: ButtonOverrides,
    *,
    pending: str,
    prompt_key: str,
) -> None:
    await callback.answer()
    await state.update_data(pending=pending)
    await state.set_state(UserActionFlow.confirming)
    await console.show(
        await content.text(prompt_key, user.language),
        confirm_keyboard(
            user.language, cb.ADMIN_USER_CONFIRM, cb.ADMIN_USER_CANCEL, danger=True, buttons=buttons
        ),
        at=callback.message,
    )


@router.callback_query(F.data == cb.ADMIN_USER_BAN, StateFilter(UserActionFlow.viewing))
async def user_ban_prompt(
    callback: CallbackQuery,
    user: User,
    content: ContentService,
    state: FSMContext,
    console: Console,
    buttons: ButtonOverrides,
) -> None:
    await _confirm(
        callback,
        user,
        content,
        state,
        console,
        buttons,
        pending="ban",
        prompt_key="admin_ban_confirm",
    )


@router.callback_query(F.data == cb.ADMIN_USER_ZERO_REFERRALS, StateFilter(UserActionFlow.viewing))
async def user_zero_prompt(
    callback: CallbackQuery,
    user: User,
    content: ContentService,
    state: FSMContext,
    console: Console,
    buttons: ButtonOverrides,
) -> None:
    await _confirm(
        callback,
        user,
        content,
        state,
        console,
        buttons,
        pending="zero_referrals",
        prompt_key="admin_zero_confirm",
    )


@router.callback_query(F.data == cb.ADMIN_USER_CONFIRM, StateFilter(UserActionFlow.confirming))
async def user_confirm(
    callback: CallbackQuery,
    user: User,
    content: ContentService,
    state: FSMContext,
    admin: AdminService,
    console: Console,
    redis: Redis,
    buttons: ButtonOverrides,
) -> None:
    await callback.answer()
    data = await state.get_data()
    target_id = data.get("target_id")
    pending = data.get("pending")
    await state.set_state(UserActionFlow.viewing)
    await state.update_data(pending=None)
    if target_id is None:
        await _back_home(callback, user, content, state, admin, console, redis, buttons)
        return
    target_id = int(target_id)
    note = None
    if pending == "ban":
        banned = await admin.ban(target_id)
        # A handle still set on a banned user is a revoke the panel did not answer for.
        pending_revoke = banned is not None and banned.panel_username is not None
        note = "admin_ban_revoke_pending" if pending_revoke else "admin_ban_done"
    elif pending == "zero_referrals":
        await admin.zero_referrals(target_id)
        note = "admin_zero_done"
    await show_card(
        console, admin, content, user, target_id, buttons, at=callback.message, note_key=note
    )


@router.callback_query(F.data == cb.ADMIN_USER_CANCEL, StateFilter(UserActionFlow.confirming))
async def user_cancel(
    callback: CallbackQuery,
    user: User,
    content: ContentService,
    state: FSMContext,
    admin: AdminService,
    console: Console,
    redis: Redis,
    buttons: ButtonOverrides,
) -> None:
    await callback.answer()
    await state.set_state(UserActionFlow.viewing)
    await state.update_data(pending=None)
    target_id = await _target(state)
    if target_id is None:
        await _back_home(callback, user, content, state, admin, console, redis, buttons)
        return
    await show_card(console, admin, content, user, target_id, buttons, at=callback.message)
