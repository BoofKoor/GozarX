"""Owner-only admin panel (Phase 6) — aiogram FSM on the shared Redis storage.

The whole router is gated by ``IsOwner`` (a non-owner's update never matches and falls through, so
the admin surface never leaks). ``/admin`` opens the menu; navigation edits that message.

Two FSM flows carry the only multi-step state (never a module-global dict):
- ``FanoutFlow``: pick broadcast/forward → the admin sends the message → it is **echoed back as a
  preview** and a "send to N users?" gate is shown → ✅ enqueues the arq ``fanout`` job, ❌ cancels.
- ``UserActionFlow``: look a user up by id → a card with per-user actions (the target id lives in
  FSM state, so the buttons stay stateless). Destructive actions (ban, zero-referrals) confirm.

Bulk work (broadcast/forward fan-out, reset-all-active) runs in the worker — handlers only enqueue.
"""

from __future__ import annotations

import logging

from aiogram import F, Router
from aiogram.filters import Command, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, Message
from arq import ArqRedis

from gozar.bot import callbacks as cb
from gozar.bot.filters import IsOwner
from gozar.bot.keyboards import (
    admin_back_keyboard,
    admin_menu_keyboard,
    admin_user_card_keyboard,
    confirm_keyboard,
)
from gozar.db.models.enums import UserStatus
from gozar.db.models.user import User
from gozar.db.repositories.user import UserRepository
from gozar.services.admin import AdminService, UserCard
from gozar.services.content import ContentService
from gozar.ui.buttons import ButtonOverrides

logger = logging.getLogger("gozar.bot.admin")

router = Router(name="admin")
router.message.filter(IsOwner())
router.callback_query.filter(IsOwner())


class FanoutFlow(StatesGroup):
    waiting_message = State()  # awaiting the admin's message to broadcast/forward
    confirming = State()  # preview shown, awaiting ✅/❌


class UserActionFlow(StatesGroup):
    waiting_id = State()  # awaiting the target telegram_id
    viewing = State()  # a user card is shown (target_id in state data)
    confirming = State()  # a destructive action's confirm is shown (pending in state data)


async def _edit(callback: CallbackQuery, text: str, markup: InlineKeyboardMarkup) -> None:
    if isinstance(callback.message, Message):
        await callback.message.edit_text(text, reply_markup=markup)


def _card_tokens(card: UserCard) -> dict[str, object]:
    u = card.user
    return {
        "id": u.telegram_id,
        "status": u.status.value,
        "language": u.language.value,
        "referrals": u.referral_count,
        "configs": card.configs,
        "panel": u.panel_username or "—",
        "joined": u.created_at.strftime("%Y-%m-%d") if u.created_at else "—",
    }


async def _to_menu(
    callback: CallbackQuery,
    user: User,
    content: ContentService,
    state: FSMContext,
    buttons: ButtonOverrides,
) -> None:
    await state.clear()
    await _edit(
        callback,
        await content.text("admin_menu", user.language),
        admin_menu_keyboard(user.language, buttons),
    )


async def _show_card(
    callback: CallbackQuery,
    user: User,
    content: ContentService,
    admin: AdminService,
    target_id: int,
    buttons: ButtonOverrides,
    *,
    note_key: str | None = None,
) -> None:
    card = await admin.lookup(target_id)
    if card is None:
        await _edit(
            callback,
            await content.text("admin_user_not_found", user.language),
            admin_back_keyboard(user.language, buttons),
        )
        return
    body = await content.text("admin_user_card", user.language, **_card_tokens(card))
    if note_key:
        body = f"{await content.text(note_key, user.language)}\n\n{body}"
    markup = admin_user_card_keyboard(
        user.language, banned=card.user.status is UserStatus.banned, buttons=buttons
    )
    await _edit(callback, body, markup)


# --- menu --------------------------------------------------------------------------------------
@router.message(Command("admin"))
async def open_admin(
    message: Message,
    user: User,
    content: ContentService,
    state: FSMContext,
    buttons: ButtonOverrides,
) -> None:
    await state.clear()
    text = await content.text("admin_menu", user.language)
    await message.answer(text, reply_markup=admin_menu_keyboard(user.language, buttons))


@router.callback_query(F.data == cb.ADMIN_MENU)
async def admin_menu(
    callback: CallbackQuery,
    user: User,
    content: ContentService,
    state: FSMContext,
    buttons: ButtonOverrides,
) -> None:
    await callback.answer()
    await _to_menu(callback, user, content, state, buttons)


@router.callback_query(F.data == cb.ADMIN_CLOSE)
async def admin_close(callback: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    await callback.answer()
    if isinstance(callback.message, Message):
        await callback.message.delete()


@router.callback_query(F.data == cb.ADMIN_STATS)
async def admin_stats(
    callback: CallbackQuery,
    user: User,
    content: ContentService,
    admin: AdminService,
    buttons: ButtonOverrides,
) -> None:
    await callback.answer()
    s = await admin.stats()
    text = await content.text(
        "admin_stats",
        user.language,
        total=s.total,
        available=s.available,
        active=s.active,
        banned=s.banned,
        configs_today=s.configs_today,
        referrals=s.referrals,
    )
    await _edit(callback, text, admin_back_keyboard(user.language, buttons))


@router.callback_query(F.data == cb.ADMIN_REFRESH_LOCATIONS)
async def admin_refresh_locations(
    callback: CallbackQuery,
    user: User,
    content: ContentService,
    admin: AdminService,
    buttons: ButtonOverrides,
) -> None:
    await callback.answer()
    names = await admin.refresh_locations()
    if names is None:
        text = await content.text("admin_refresh_failed", user.language)
    else:
        text = await content.text(
            "admin_refresh_done",
            user.language,
            count=len(names),
            locations=", ".join(names) or "—",
        )
    await _edit(callback, text, admin_back_keyboard(user.language, buttons))


# --- broadcast / forward (preview + confirm gate, then enqueue) --------------------------------
@router.callback_query(F.data == cb.ADMIN_BROADCAST)
async def start_broadcast(
    callback: CallbackQuery,
    user: User,
    content: ContentService,
    state: FSMContext,
    buttons: ButtonOverrides,
) -> None:
    await callback.answer()
    await state.set_state(FanoutFlow.waiting_message)
    await state.update_data(action="broadcast")
    await _edit(
        callback,
        await content.text("admin_broadcast_prompt", user.language),
        admin_back_keyboard(user.language, buttons),
    )


@router.callback_query(F.data == cb.ADMIN_FORWARD)
async def start_forward(
    callback: CallbackQuery,
    user: User,
    content: ContentService,
    state: FSMContext,
    buttons: ButtonOverrides,
) -> None:
    await callback.answer()
    await state.set_state(FanoutFlow.waiting_message)
    await state.update_data(action="forward")
    await _edit(
        callback,
        await content.text("admin_forward_prompt", user.language),
        admin_back_keyboard(user.language, buttons),
    )


@router.message(StateFilter(FanoutFlow.waiting_message))
async def fanout_receive(
    message: Message,
    user: User,
    content: ContentService,
    state: FSMContext,
    user_repo: UserRepository,
    buttons: ButtonOverrides,
) -> None:
    data = await state.get_data()
    action = data.get("action", "broadcast")
    await state.update_data(src_chat=message.chat.id, message_id=message.message_id)
    await state.set_state(FanoutFlow.confirming)
    # Echo the message back exactly as users will see it (copy = clean, forward = keeps the header).
    try:
        if action == "forward":
            await message.forward(message.chat.id)
        else:
            await message.copy_to(message.chat.id)
    except Exception:
        logger.warning("admin fan-out preview echo failed")
    total = await user_repo.count()
    text = await content.text("admin_send_preview", user.language, count=total)
    await message.answer(
        text,
        reply_markup=confirm_keyboard(
            user.language,
            cb.ADMIN_SEND_CONFIRM,
            cb.ADMIN_SEND_CANCEL,
            confirm_key="admin_send",
            buttons=buttons,
        ),
    )


@router.callback_query(F.data == cb.ADMIN_SEND_CONFIRM, StateFilter(FanoutFlow.confirming))
async def fanout_confirm(
    callback: CallbackQuery,
    user: User,
    content: ContentService,
    state: FSMContext,
    arq: ArqRedis | None,
    buttons: ButtonOverrides,
) -> None:
    await callback.answer()
    data = await state.get_data()
    await state.clear()
    action = data.get("action", "broadcast")
    src_chat = data.get("src_chat")
    message_id = data.get("message_id")
    if arq is None or src_chat is None or message_id is None or callback.from_user is None:
        await _edit(
            callback,
            await content.text("admin_send_failed", user.language),
            admin_back_keyboard(user.language, buttons),
        )
        return
    await arq.enqueue_job("fanout", action, src_chat, message_id, callback.from_user.id)
    await _edit(
        callback,
        await content.text("admin_send_queued", user.language),
        admin_back_keyboard(user.language, buttons),
    )


@router.callback_query(F.data == cb.ADMIN_SEND_CANCEL, StateFilter(FanoutFlow.confirming))
async def fanout_cancel(
    callback: CallbackQuery,
    user: User,
    content: ContentService,
    state: FSMContext,
    buttons: ButtonOverrides,
) -> None:
    await callback.answer()
    await state.clear()
    await _edit(
        callback,
        await content.text("admin_send_cancelled", user.language),
        admin_back_keyboard(user.language, buttons),
    )


# --- user lookup + per-user actions ------------------------------------------------------------
@router.callback_query(F.data == cb.ADMIN_USERS)
async def start_user_lookup(
    callback: CallbackQuery,
    user: User,
    content: ContentService,
    state: FSMContext,
    buttons: ButtonOverrides,
) -> None:
    await callback.answer()
    await state.set_state(UserActionFlow.waiting_id)
    await _edit(
        callback,
        await content.text("admin_user_prompt", user.language),
        admin_back_keyboard(user.language, buttons),
    )


@router.message(StateFilter(UserActionFlow.waiting_id))
async def user_lookup(
    message: Message,
    user: User,
    content: ContentService,
    state: FSMContext,
    admin: AdminService,
    buttons: ButtonOverrides,
) -> None:
    raw = (message.text or "").strip()
    card = None
    if raw.lstrip("-").isdigit():
        card = await admin.lookup(int(raw))
    if card is None:
        await message.answer(
            await content.text("admin_user_not_found", user.language),
            reply_markup=admin_back_keyboard(user.language, buttons),
        )
        return
    await state.set_state(UserActionFlow.viewing)
    await state.update_data(target_id=card.user.telegram_id)
    body = await content.text("admin_user_card", user.language, **_card_tokens(card))
    await message.answer(
        body,
        reply_markup=admin_user_card_keyboard(
            user.language, banned=card.user.status is UserStatus.banned, buttons=buttons
        ),
    )


async def _target(state: FSMContext) -> int | None:
    data = await state.get_data()
    target_id = data.get("target_id")
    return int(target_id) if target_id is not None else None


@router.callback_query(F.data == cb.ADMIN_USER_UNBAN, StateFilter(UserActionFlow.viewing))
async def user_unban(
    callback: CallbackQuery,
    user: User,
    content: ContentService,
    state: FSMContext,
    admin: AdminService,
    buttons: ButtonOverrides,
) -> None:
    await callback.answer()
    target_id = await _target(state)
    if target_id is None:
        await _to_menu(callback, user, content, state, buttons)
        return
    await admin.unban(target_id)
    await _show_card(
        callback, user, content, admin, target_id, buttons, note_key="admin_unban_done"
    )


@router.callback_query(F.data == cb.ADMIN_USER_RECLAIM, StateFilter(UserActionFlow.viewing))
async def user_reclaim(
    callback: CallbackQuery,
    user: User,
    content: ContentService,
    state: FSMContext,
    admin: AdminService,
    buttons: ButtonOverrides,
) -> None:
    await callback.answer()
    target_id = await _target(state)
    if target_id is None:
        await _to_menu(callback, user, content, state, buttons)
        return
    await admin.reclaim(target_id)
    await _show_card(
        callback, user, content, admin, target_id, buttons, note_key="admin_reclaim_done"
    )


@router.callback_query(F.data == cb.ADMIN_USER_BAN, StateFilter(UserActionFlow.viewing))
async def user_ban_prompt(
    callback: CallbackQuery,
    user: User,
    content: ContentService,
    state: FSMContext,
    buttons: ButtonOverrides,
) -> None:
    await callback.answer()
    await state.update_data(pending="ban")
    await state.set_state(UserActionFlow.confirming)
    await _edit(
        callback,
        await content.text("admin_ban_confirm", user.language),
        confirm_keyboard(
            user.language, cb.ADMIN_USER_CONFIRM, cb.ADMIN_USER_CANCEL, buttons=buttons
        ),
    )


@router.callback_query(F.data == cb.ADMIN_USER_ZERO_REFERRALS, StateFilter(UserActionFlow.viewing))
async def user_zero_prompt(
    callback: CallbackQuery,
    user: User,
    content: ContentService,
    state: FSMContext,
    buttons: ButtonOverrides,
) -> None:
    await callback.answer()
    await state.update_data(pending="zero_referrals")
    await state.set_state(UserActionFlow.confirming)
    await _edit(
        callback,
        await content.text("admin_zero_confirm", user.language),
        confirm_keyboard(
            user.language, cb.ADMIN_USER_CONFIRM, cb.ADMIN_USER_CANCEL, buttons=buttons
        ),
    )


@router.callback_query(F.data == cb.ADMIN_USER_CONFIRM, StateFilter(UserActionFlow.confirming))
async def user_confirm(
    callback: CallbackQuery,
    user: User,
    content: ContentService,
    state: FSMContext,
    admin: AdminService,
    buttons: ButtonOverrides,
) -> None:
    await callback.answer()
    data = await state.get_data()
    target_id = data.get("target_id")
    pending = data.get("pending")
    await state.set_state(UserActionFlow.viewing)
    await state.update_data(pending=None)
    if target_id is None:
        await _to_menu(callback, user, content, state, buttons)
        return
    target_id = int(target_id)
    note = None
    if pending == "ban":
        await admin.ban(target_id)
        note = "admin_ban_done"
    elif pending == "zero_referrals":
        await admin.zero_referrals(target_id)
        note = "admin_zero_done"
    await _show_card(callback, user, content, admin, target_id, buttons, note_key=note)


@router.callback_query(F.data == cb.ADMIN_USER_CANCEL, StateFilter(UserActionFlow.confirming))
async def user_cancel(
    callback: CallbackQuery,
    user: User,
    content: ContentService,
    state: FSMContext,
    admin: AdminService,
    buttons: ButtonOverrides,
) -> None:
    await callback.answer()
    await state.set_state(UserActionFlow.viewing)
    await state.update_data(pending=None)
    target_id = await _target(state)
    if target_id is None:
        await _to_menu(callback, user, content, state, buttons)
        return
    await _show_card(callback, user, content, admin, target_id, buttons)


# --- bulk reset all active ---------------------------------------------------------------------
@router.callback_query(F.data == cb.ADMIN_RESET_ALL)
async def reset_all_prompt(
    callback: CallbackQuery,
    user: User,
    content: ContentService,
    admin: AdminService,
    buttons: ButtonOverrides,
) -> None:
    await callback.answer()
    s = await admin.stats()
    text = await content.text("admin_reset_all_confirm", user.language, count=s.active)
    await _edit(
        callback,
        text,
        confirm_keyboard(user.language, cb.ADMIN_RESET_ALL_CONFIRM, cb.ADMIN_MENU, buttons=buttons),
    )


@router.callback_query(F.data == cb.ADMIN_RESET_ALL_CONFIRM)
async def reset_all_confirm(
    callback: CallbackQuery,
    user: User,
    content: ContentService,
    arq: ArqRedis | None,
    buttons: ButtonOverrides,
) -> None:
    await callback.answer()
    if arq is None or callback.from_user is None:
        await _edit(
            callback,
            await content.text("admin_send_failed", user.language),
            admin_back_keyboard(user.language, buttons),
        )
        return
    await arq.enqueue_job("reset_all_active", callback.from_user.id)
    await _edit(
        callback,
        await content.text("admin_reset_all_queued", user.language),
        admin_back_keyboard(user.language, buttons),
    )
