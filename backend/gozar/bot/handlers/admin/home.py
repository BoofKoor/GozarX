"""Console home: ``/admin`` (a fresh screen at the bottom), «🔙 admin menu», ❌ close.

The home is a summary first — users, today's configs, active configs, the trial squad online — all
from the DB and the worker's last squad reading in Redis, so opening it never waits on the panel.
"""

from __future__ import annotations

from datetime import UTC, datetime

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from redis.asyncio import Redis

from gozar.bot import callbacks as cb
from gozar.bot.handlers.admin.console import Console
from gozar.bot.keyboards import admin_menu_keyboard
from gozar.db.models.user import User
from gozar.services.admin import AdminService
from gozar.services.content import ContentService
from gozar.services.panel_cache import read_squad_online
from gozar.ui.buttons import ButtonOverrides
from gozar.ui.console_text import tr
from gozar.ui.fmt import num, when
from gozar.ui.rich import Doc
from gozar.ui.theme import NOOP

router = Router(name="admin.home")


async def home_doc(
    user: User, content: ContentService, admin: AdminService, console: Console, redis: Redis
) -> Doc:
    lang = user.language
    figures = await admin.home()
    online = await read_squad_online(redis)
    doc = Doc().h(tr("home_title", lang), 2)
    if await console.looks.take_notice() == "blocked":
        doc.quote(tr("notice_blocked", lang))
    rows: list[tuple[str, str] | None] = [
        (
            tr("home_users", lang),
            tr(
                "home_users_val",
                lang,
                total=num(figures.total, lang),
                new=num(figures.new_today, lang),
            ),
        ),
        (tr("home_claims", lang), num(figures.claims_today, lang)),
        (tr("home_active", lang), num(figures.active, lang)),
        (
            (
                tr("home_online", lang),
                tr(
                    "home_online_val",
                    lang,
                    now=num(online.count, lang),
                    week=num(online.week, lang),
                ),
            )
            if online is not None
            else None
        ),
    ]
    doc.kv(rows)
    doc.p(await content.text("admin_menu", lang))
    doc.footer(tr("home_footer", lang, time=when(datetime.now(UTC), lang, "t")))
    return doc


async def show_home(
    user: User,
    content: ContentService,
    admin: AdminService,
    console: Console,
    redis: Redis,
    buttons: ButtonOverrides,
    *,
    at: object = None,
    new: bool = False,
) -> None:
    doc = await home_doc(user, content, admin, console, redis)
    await console.show(doc, admin_menu_keyboard(user.language, buttons), at=at, new=new)


@router.message(Command("admin"))
async def open_admin(
    message: Message,
    user: User,
    content: ContentService,
    state: FSMContext,
    admin: AdminService,
    console: Console,
    redis: Redis,
    buttons: ButtonOverrides,
) -> None:
    await state.clear()
    await console.consume(message)
    await show_home(user, content, admin, console, redis, buttons, new=True)


@router.callback_query(F.data == cb.ADMIN_MENU)
async def admin_menu(
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
    await state.clear()
    await show_home(user, content, admin, console, redis, buttons, at=callback.message)


@router.callback_query(F.data == cb.ADMIN_CLOSE)
async def admin_close(callback: CallbackQuery, state: FSMContext, console: Console) -> None:
    await state.clear()
    await callback.answer()
    await console.close(at=callback.message)


@router.callback_query(F.data == NOOP)
async def info_only(callback: CallbackQuery) -> None:
    """A cell that only shows something (drawn disabled; an old client may still send it)."""
    await callback.answer()
