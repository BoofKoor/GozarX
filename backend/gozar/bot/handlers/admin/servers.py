"""🗄 Servers: every server the bot has logged into once, opened since with its own key.

A server is saved by its first login — ➕ node, ➕ server, or 🔗 on a panel node — and from then on
needs no password. Its card tests the connection, makes it a node, accepts a new SSH host key (after
asking: a changed key can mean someone else answers on that address), or forgets it — taking the
bot's key back off the server first, so a forgotten server keeps nothing of the bot.
"""

from __future__ import annotations

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery
from arq import ArqRedis
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from gozar.bot import callbacks as cb
from gozar.bot import ops_view
from gozar.bot.handlers.admin.console import Console
from gozar.bot.handlers.admin.nodes import OpsFlow, prepare_server, start_job, vault_ready
from gozar.db.models.ops import OpsServer
from gozar.db.models.user import User
from gozar.db.repositories.ops import OpsServerRepository
from gozar.services.ops import JobKind
from gozar.ui.buttons import ButtonOverrides
from gozar.ui.rich import Doc

router = Router(name="admin.servers")


def _id(data: str | None, prefix: str) -> int | None:
    raw = (data or "").removeprefix(prefix).split(":", 1)[0]
    return int(raw) if raw.isdigit() else None


async def _server(
    callback: CallbackQuery,
    session: AsyncSession,
    console: Console,
    buttons: ButtonOverrides,
    prefix: str,
) -> OpsServer | None:
    """The server a button is about — or the list again, saying it is gone."""
    sid = _id(callback.data, prefix)
    server = await OpsServerRepository(session).get(sid) if sid is not None else None
    if server is None:
        notice = "این سرور دیگر نیست."
        await show_servers(console, session, buttons, at=callback.message, notice=notice)
    return server


async def show_servers(
    console: Console,
    session: AsyncSession,
    buttons: ButtonOverrides,
    *,
    at: object = None,
    notice: str = "",
) -> None:
    servers = await OpsServerRepository(session).all()
    doc, markup = ops_view.servers_screen(servers, lang=console.lang, buttons=buttons)
    if notice:
        doc = Doc().quote(notice).extend(doc)
    await console.show(doc, markup, at=at)


@router.callback_query(F.data == cb.OPS_SERVERS)
async def servers_list(
    callback: CallbackQuery,
    state: FSMContext,
    console: Console,
    session: AsyncSession,
    buttons: ButtonOverrides,
) -> None:
    await callback.answer()
    await state.clear()
    await show_servers(console, session, buttons, at=callback.message)


@router.callback_query(F.data == cb.OPS_SERVERS_ADD)
async def server_add(
    callback: CallbackQuery, state: FSMContext, console: Console, buttons: ButtonOverrides
) -> None:
    await callback.answer()
    if not await vault_ready(console, buttons, callback.message):
        return
    await state.set_state(OpsFlow.address)
    await state.update_data(for_node=False)
    screen = ops_view.address_prompt(for_node=False, lang=console.lang, buttons=buttons)
    await console.show(*screen, at=callback.message)


@router.callback_query(F.data.startswith(cb.OPS_SERVER_OPEN))
async def server_open(
    callback: CallbackQuery,
    state: FSMContext,
    console: Console,
    session: AsyncSession,
    buttons: ButtonOverrides,
) -> None:
    await callback.answer()
    await state.clear()
    server = await _server(callback, session, console, buttons, cb.OPS_SERVER_OPEN)
    if server is not None:
        screen = ops_view.server_screen(server, lang=console.lang, buttons=buttons)
        await console.show(*screen, at=callback.message)


@router.callback_query(F.data.startswith(cb.OPS_SERVER_TEST))
async def server_test(
    callback: CallbackQuery,
    console: Console,
    session: AsyncSession,
    redis: Redis,
    arq: ArqRedis | None,
    user: User,
    buttons: ButtonOverrides,
) -> None:
    await callback.answer()
    server = await _server(callback, session, console, buttons, cb.OPS_SERVER_TEST)
    if server is None or not await vault_ready(console, buttons, callback.message):
        return
    await start_job(
        console,
        session,
        redis,
        arq,
        user,
        buttons,
        kind=JobKind.server_test,
        params={"server_id": server.id},
        at=callback.message,
    )


@router.callback_query(F.data.startswith(cb.OPS_SERVER_NODE))
async def server_node(
    callback: CallbackQuery,
    state: FSMContext,
    console: Console,
    session: AsyncSession,
    redis: Redis,
    arq: ArqRedis | None,
    user: User,
    buttons: ButtonOverrides,
) -> None:
    """🖥 on a saved server (its card, the ➕ node prompt, or 🔁 on a summary)."""
    await callback.answer()
    server = await _server(callback, session, console, buttons, cb.OPS_SERVER_NODE)
    if server is None or not await vault_ready(console, buttons, callback.message):
        return
    await prepare_server(
        console, session, redis, arq, user, state, buttons, server, at=callback.message
    )


@router.callback_query(F.data.startswith(cb.OPS_SERVER_FORGET_OK))
async def server_forget_ok(
    callback: CallbackQuery,
    console: Console,
    session: AsyncSession,
    redis: Redis,
    arq: ArqRedis | None,
    user: User,
    buttons: ButtonOverrides,
) -> None:
    await callback.answer()
    server = await _server(callback, session, console, buttons, cb.OPS_SERVER_FORGET_OK)
    if server is None:
        return
    if not server.key_ok:  # the bot can't get in to take its key back: nothing to wait for
        label = server.label
        await OpsServerRepository(session).delete(server)
        notice = (
            f"«{label}» فراموش شد. کلید ربات بازش نمی‌کرد، پس اگر هنوز روی سرور است دستی پاکش کن."
        )
        await show_servers(console, session, buttons, at=callback.message, notice=notice)
        return
    if not await vault_ready(console, buttons, callback.message):
        return
    await start_job(
        console,
        session,
        redis,
        arq,
        user,
        buttons,
        kind=JobKind.server_forget,
        params={"server_id": server.id},
        at=callback.message,
    )


@router.callback_query(F.data.startswith(cb.OPS_SERVER_FORGET))
async def server_forget(
    callback: CallbackQuery,
    console: Console,
    session: AsyncSession,
    buttons: ButtonOverrides,
) -> None:
    await callback.answer()
    server = await _server(callback, session, console, buttons, cb.OPS_SERVER_FORGET)
    if server is not None:
        screen = ops_view.forget_confirm(server, lang=console.lang, buttons=buttons)
        await console.show(*screen, at=callback.message)


@router.callback_query(F.data.startswith(cb.OPS_SERVER_DROP))
async def server_drop(
    callback: CallbackQuery,
    console: Console,
    session: AsyncSession,
    buttons: ButtonOverrides,
) -> None:
    """Forget a server the bot could not get into (its forget job failed): the row only."""
    await callback.answer()
    server = await _server(callback, session, console, buttons, cb.OPS_SERVER_DROP)
    if server is None:
        return
    label = server.label
    await OpsServerRepository(session).delete(server)
    notice = f"«{label}» فراموش شد؛ کلید ربات اگر هنوز روی سرور است دستی پاکش کن."
    await show_servers(console, session, buttons, at=callback.message, notice=notice)


@router.callback_query(F.data.startswith(cb.OPS_SERVER_TRUST))
async def server_trust(
    callback: CallbackQuery,
    console: Console,
    session: AsyncSession,
    buttons: ButtonOverrides,
) -> None:
    """A changed SSH host key: confirm first, then the next login pins whatever the server shows."""
    await callback.answer()
    server = await _server(callback, session, console, buttons, cb.OPS_SERVER_TRUST)
    if server is None:
        return
    if not (callback.data or "").endswith(":ok"):
        screen = ops_view.trust_confirm(server, lang=console.lang, buttons=buttons)
        await console.show(*screen, at=callback.message)
        return
    await OpsServerRepository(session).unpin(server)
    doc, markup = ops_view.server_screen(server, lang=console.lang, buttons=buttons)
    notice = "♻️ ورود بعدی کلید تازهٔ سرور را می‌پذیرد و همان را نگه می‌دارد. «🔌 تست اتصال» را بزن."
    await console.show(Doc().quote(notice).extend(doc), markup, at=callback.message)
