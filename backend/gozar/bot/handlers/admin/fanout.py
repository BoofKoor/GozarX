"""📣 Broadcast / ↪️ forward to every user, and ♻️ reset everyone's traffic — all sent by the worker.

``FanoutFlow``: pick broadcast or forward → the admin sends the message → it is echoed back as the
users will see it (copy = clean, forward = keeps its header) → a "send to N users?" gate → ✅
enqueues the arq ``fanout`` job, ❌ cancels. The admin's message is the copy SOURCE, so unlike every
other typed answer in the console it is NOT deleted: the worker copies it to each user. The gate is
a new screen under the preview (the prompt above it is removed), so "the preview above" holds.
"""

from __future__ import annotations

import logging

from aiogram import F, Router
from aiogram.filters import StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message
from arq import ArqRedis

from gozar.bot import callbacks as cb
from gozar.bot.handlers.admin.console import Console
from gozar.bot.keyboards import admin_back_keyboard, confirm_keyboard
from gozar.db.models.user import User
from gozar.db.repositories.user import UserRepository
from gozar.services.admin import AdminService
from gozar.services.content import ContentService
from gozar.ui.buttons import ButtonOverrides

logger = logging.getLogger("gozar.bot.admin")

router = Router(name="admin.fanout")


class FanoutFlow(StatesGroup):
    waiting_message = State()  # awaiting the admin's message to broadcast/forward
    confirming = State()  # preview shown, awaiting ✅/❌


async def _prompt(
    callback: CallbackQuery,
    user: User,
    content: ContentService,
    state: FSMContext,
    console: Console,
    buttons: ButtonOverrides,
    *,
    action: str,
) -> None:
    await callback.answer()
    await state.set_state(FanoutFlow.waiting_message)
    await state.update_data(action=action)
    key = "admin_forward_prompt" if action == "forward" else "admin_broadcast_prompt"
    await console.show(
        await content.text(key, user.language),
        admin_back_keyboard(user.language, buttons),
        at=callback.message,
    )


@router.callback_query(F.data == cb.ADMIN_BROADCAST)
async def start_broadcast(
    callback: CallbackQuery,
    user: User,
    content: ContentService,
    state: FSMContext,
    console: Console,
    buttons: ButtonOverrides,
) -> None:
    await _prompt(callback, user, content, state, console, buttons, action="broadcast")


@router.callback_query(F.data == cb.ADMIN_FORWARD)
async def start_forward(
    callback: CallbackQuery,
    user: User,
    content: ContentService,
    state: FSMContext,
    console: Console,
    buttons: ButtonOverrides,
) -> None:
    await _prompt(callback, user, content, state, console, buttons, action="forward")


@router.message(StateFilter(FanoutFlow.waiting_message))
async def fanout_receive(
    message: Message,
    user: User,
    content: ContentService,
    state: FSMContext,
    user_repo: UserRepository,
    console: Console,
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
    await console.show(
        await content.text("admin_send_preview", user.language, count=total),
        confirm_keyboard(
            user.language,
            cb.ADMIN_SEND_CONFIRM,
            cb.ADMIN_SEND_CANCEL,
            confirm_key="admin_send",
            buttons=buttons,
        ),
        new=True,
    )


@router.callback_query(F.data == cb.ADMIN_SEND_CONFIRM, StateFilter(FanoutFlow.confirming))
async def fanout_confirm(
    callback: CallbackQuery,
    user: User,
    content: ContentService,
    state: FSMContext,
    arq: ArqRedis | None,
    console: Console,
    buttons: ButtonOverrides,
) -> None:
    await callback.answer()
    data = await state.get_data()
    await state.clear()
    action = data.get("action", "broadcast")
    src_chat = data.get("src_chat")
    message_id = data.get("message_id")
    lang = user.language
    if arq is None or src_chat is None or message_id is None or callback.from_user is None:
        await console.show(
            await content.text("admin_send_failed", lang),
            admin_back_keyboard(lang, buttons),
            at=callback.message,
        )
        return
    await arq.enqueue_job("fanout", action, src_chat, message_id, callback.from_user.id)
    await console.show(
        await content.text("admin_send_queued", lang),
        admin_back_keyboard(lang, buttons),
        at=callback.message,
    )


@router.callback_query(F.data == cb.ADMIN_SEND_CANCEL, StateFilter(FanoutFlow.confirming))
async def fanout_cancel(
    callback: CallbackQuery,
    user: User,
    content: ContentService,
    state: FSMContext,
    console: Console,
    buttons: ButtonOverrides,
) -> None:
    await callback.answer()
    await state.clear()
    await console.show(
        await content.text("admin_send_cancelled", user.language),
        admin_back_keyboard(user.language, buttons),
        at=callback.message,
    )


# --- ♻️ reset everyone's traffic (the worker walks the active users) ----------------------------
@router.callback_query(F.data == cb.ADMIN_RESET_ALL)
async def reset_all_prompt(
    callback: CallbackQuery,
    user: User,
    content: ContentService,
    admin: AdminService,
    console: Console,
    buttons: ButtonOverrides,
) -> None:
    await callback.answer()
    s = await admin.stats()
    await console.show(
        await content.text("admin_reset_all_confirm", user.language, count=s.active),
        confirm_keyboard(
            user.language, cb.ADMIN_RESET_ALL_CONFIRM, cb.ADMIN_MENU, danger=True, buttons=buttons
        ),
        at=callback.message,
    )


@router.callback_query(F.data == cb.ADMIN_RESET_ALL_CONFIRM)
async def reset_all_confirm(
    callback: CallbackQuery,
    user: User,
    content: ContentService,
    arq: ArqRedis | None,
    console: Console,
    buttons: ButtonOverrides,
) -> None:
    await callback.answer()
    lang = user.language
    if arq is None or callback.from_user is None:
        await console.show(
            await content.text("admin_send_failed", lang),
            admin_back_keyboard(lang, buttons),
            at=callback.message,
        )
        return
    await arq.enqueue_job("reset_all_active", callback.from_user.id)
    await console.show(
        await content.text("admin_reset_all_queued", lang),
        admin_back_keyboard(lang, buttons),
        at=callback.message,
    )
