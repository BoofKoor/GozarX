"""🖥 Nodes: the panel's nodes, and turning a server into one — over SSH, from the console.

The SSH work never runs here: a handler writes an ``ops_jobs`` row and queues it
(``services/ops.enqueue``), the worker does it while the console message shows every step
(``worker/ops``), and the job's last screen offers what comes next. One job at a time per chat.

➕ node: the admin sends the server's SSH address, then — unless the bot's key already opens it —
its password, which is deleted from the chat as soon as it is read and handed to the worker for that
one job (sealed, read once, ``SECRET_TTL``). Never in FSM data, never on the job row, never in a
log. The prepare job leaves a draft (``services/node_draft``) the admin can change — name, country,
config profile — in FSM data, before ✅ queues the install.
"""

from __future__ import annotations

import logging

from aiogram import Bot, F, Router
from aiogram.filters import StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import BufferedInputFile, CallbackQuery, Message
from arq import ArqRedis
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from gozar import vault
from gozar.bot import callbacks as cb
from gozar.bot import ops_view
from gozar.bot.handlers.admin.console import Console
from gozar.db.models.ops import OpsJob, OpsJobStatus, OpsServer
from gozar.db.models.user import User
from gozar.db.repositories.ops import OpsJobRepository, OpsServerRepository
from gozar.remnawave import RemnawaveClient
from gozar.remnawave.ops import NodeInfo, PanelError
from gozar.services.node_draft import NodeDraft
from gozar.services.ops import JobKind, Target, active_job, enqueue
from gozar.ui.buttons import ButtonOverrides
from gozar.ui.flags import country_code
from gozar.ui.rich import Doc, esc

logger = logging.getLogger("gozar.bot.admin.nodes")

router = Router(name="admin.nodes")

#: A list read in a handler waits this long for the panel (the webhook waits on the handler).
PANEL_TIMEOUT = 10.0


class OpsFlow(StatesGroup):
    address = State()  # waiting for an SSH address (data: for_node)
    password = State()  # waiting for a password (data: purpose + what it is for)
    name = State()  # waiting for a node name (data: draft_job, draft)
    country = State()  # waiting for a country (data: draft_job, draft)


# ---- shared by the 🖥 and 🗄 sections ------------------------
async def start_job(
    console: Console,
    session: AsyncSession,
    redis: Redis,
    arq: ArqRedis | None,
    user: User,
    buttons: ButtonOverrides,
    *,
    kind: str,
    params: dict,
    secret: str | None = None,
    at: object = None,
) -> OpsJob | None:
    """Queue a job on the live screen (it becomes the job's progress message). None — with a
    screen saying why — when another job is still in flight, or the worker can't be reached."""
    lang = console.lang
    busy = await active_job(session, console.chat_id)
    if busy is not None:
        await console.show(*ops_view.busy_screen(busy, lang=lang, buttons=buttons), at=at)
        return None
    if arq is None:
        doc = Doc().h("⚠️ worker در دسترس نیست", 3).p("کارهای SSH را worker انجام می‌دهد.")
        await console.show(doc, ops_view.keyboard([], lang=lang, buttons=buttons), at=at)
        return None
    title = ops_view.TITLES.get(kind, "⏳")
    shown = await console.show(*ops_view.queued_screen(title, lang=lang, buttons=buttons), at=at)
    message_id = shown.message_id if shown is not None else await console.store.get(console.chat_id)
    try:
        return await enqueue(
            session,
            redis,
            arq,
            kind=kind,
            params=params,
            chat_id=console.chat_id,
            message_id=message_id,
            lang=lang.value,
            admin_id=user.telegram_id,
            secret=secret,
        )
    except Exception:
        logger.exception("could not queue ops job %s", kind)
        doc = Doc().h("⚠️ کار در صف نرفت", 3).p("دوباره امتحان کن.")
        await console.show(doc, ops_view.keyboard([], lang=lang, buttons=buttons))
        return None


async def vault_ready(console: Console, buttons: ButtonOverrides, at: object) -> bool:
    """SSH needs VAULT_KEY (the bot's key is kept sealed with it); say so when it is missing."""
    if vault.available():
        return True
    await console.show(*ops_view.vault_missing(lang=console.lang, buttons=buttons), at=at)
    return False


async def ask_password(
    console: Console,
    state: FSMContext,
    buttons: ButtonOverrides,
    *,
    login: str,
    purpose: str,
    data: dict,
    why: str = "",
    back: str = cb.OPS_NODES,
    at: object = None,
) -> None:
    await state.set_state(OpsFlow.password)
    await state.update_data(purpose=purpose, **data)
    screen = ops_view.password_prompt(login, why=why, back=back, lang=console.lang, buttons=buttons)
    await console.show(*screen, at=at)


async def prepare_server(
    console: Console,
    session: AsyncSession,
    redis: Redis,
    arq: ArqRedis | None,
    user: User,
    state: FSMContext,
    buttons: ButtonOverrides,
    server: OpsServer,
    *,
    at: object = None,
) -> None:
    """🖥 on a saved server: straight in with the bot's key, or ask its password first."""
    if not server.key_ok:
        await ask_password(
            console,
            state,
            buttons,
            login=server.address,
            purpose=JobKind.node_prepare,
            data={"server_id": server.id},
            why=(
                "کلید ربات دیگر این سرور را باز نمی‌کند؛ با رمز یک بار وارد می‌شوم و کلید را"
                " دوباره می‌گذارم."
            ),
            at=at,
        )
        return
    await state.clear()
    await start_job(
        console,
        session,
        redis,
        arq,
        user,
        buttons,
        kind=JobKind.node_prepare,
        params={"server_id": server.id},
        at=at,
    )


# ---- 🖥 the list ------------------------
async def show_nodes(
    console: Console,
    session: AsyncSession,
    panel: RemnawaveClient,
    buttons: ButtonOverrides,
    *,
    at: object = None,
) -> None:
    nodes: list[NodeInfo] | None = None
    error = ""
    try:
        nodes = await panel.ops(timeout=PANEL_TIMEOUT).nodes()
    except PanelError as e:
        error = e.message
    saved = await OpsServerRepository(session).by_addresses({n.address for n in nodes or []})
    screen = ops_view.nodes_screen(nodes, saved, error=error, lang=console.lang, buttons=buttons)
    await console.show(*screen, at=at)


@router.callback_query(F.data == cb.OPS_NODES)
async def nodes_list(
    callback: CallbackQuery,
    state: FSMContext,
    console: Console,
    session: AsyncSession,
    panel: RemnawaveClient,
    buttons: ButtonOverrides,
) -> None:
    await callback.answer()
    await state.clear()
    await show_nodes(console, session, panel, buttons, at=callback.message)


@router.callback_query(F.data == cb.OPS_NODES_ADD)
async def node_add(
    callback: CallbackQuery,
    state: FSMContext,
    console: Console,
    session: AsyncSession,
    buttons: ButtonOverrides,
) -> None:
    await callback.answer()
    if not await vault_ready(console, buttons, callback.message):
        return
    await state.set_state(OpsFlow.address)
    await state.update_data(for_node=True)
    servers = await OpsServerRepository(session).all()
    screen = ops_view.address_prompt(
        for_node=True, servers=servers, lang=console.lang, buttons=buttons
    )
    await console.show(*screen, at=callback.message)


@router.message(StateFilter(OpsFlow.address))
async def address_typed(
    message: Message,
    state: FSMContext,
    console: Console,
    session: AsyncSession,
    redis: Redis,
    arq: ArqRedis | None,
    user: User,
    buttons: ButtonOverrides,
) -> None:
    await console.consume(message)
    data = await state.get_data()
    for_node = bool(data.get("for_node", True))
    target = Target.parse(message.text or "")
    if target is None:
        servers = await OpsServerRepository(session).all() if for_node else []
        screen = ops_view.address_prompt(
            for_node=for_node,
            servers=servers,
            problem="این آدرس SSH خوانده نشد؛ مثل نمونه‌ها بفرست.",
            lang=console.lang,
            buttons=buttons,
        )
        await console.show(*screen)
        return
    saved = await OpsServerRepository(session).find(target.host, target.port, target.username)
    if for_node and saved is not None and saved.key_ok:
        await prepare_server(console, session, redis, arq, user, state, buttons, saved)
        return
    if not for_node and saved is not None and saved.key_ok:
        await state.clear()
        screen = ops_view.server_screen(saved, lang=console.lang, buttons=buttons)
        await console.show(Doc().quote("این سرور از قبل ذخیره است.").extend(screen[0]), screen[1])
        return
    await ask_password(
        console,
        state,
        buttons,
        login=target.text,
        purpose=JobKind.node_prepare if for_node else JobKind.server_add,
        data={"target": target.params()},
        back=cb.OPS_NODES if for_node else cb.OPS_SERVERS,
    )


@router.message(StateFilter(OpsFlow.password))
async def password_typed(
    message: Message,
    state: FSMContext,
    console: Console,
    session: AsyncSession,
    redis: Redis,
    arq: ArqRedis | None,
    user: User,
    buttons: ButtonOverrides,
) -> None:
    # the password leaves the chat before anything else can go wrong
    await console.consume(message)
    secret = message.text or ""
    data = await state.get_data()
    purpose = data.get("purpose")
    if not secret.strip() or purpose not in (
        JobKind.node_prepare,
        JobKind.server_add,
        JobKind.node_install,
    ):
        await state.clear()
        await console.show(*ops_view.unknown_job(lang=console.lang, buttons=buttons))
        return
    if purpose == JobKind.node_install:
        params = {"draft": data["draft"]}
    elif data.get("server_id") is not None:
        params = {"server_id": int(data["server_id"])}
    else:
        params = dict(data["target"])
    await state.clear()
    await start_job(
        console, session, redis, arq, user, buttons, kind=purpose, params=params, secret=secret
    )


@router.callback_query(F.data.startswith(cb.OPS_NODE_SSH))
async def node_ssh(
    callback: CallbackQuery,
    state: FSMContext,
    console: Console,
    panel: RemnawaveClient,
    buttons: ButtonOverrides,
) -> None:
    """🔗 an existing node: save its server in the bot (one login with its password)."""
    await callback.answer()
    if not await vault_ready(console, buttons, callback.message):
        return
    uuid = (callback.data or "").removeprefix(cb.OPS_NODE_SSH)
    try:
        node = await panel.ops(timeout=PANEL_TIMEOUT).node(uuid)
    except PanelError as e:
        await callback.answer(e.message[:180], show_alert=True)
        return
    target = Target.parse(node.address)
    if target is None:
        await callback.answer("آدرس این نود آدرس SSH نیست", show_alert=True)
        return
    await ask_password(
        console,
        state,
        buttons,
        login=target.text,
        purpose=JobKind.server_add,
        data={"target": target.params()},
        why=(
            f"نود «{node.name}». اگر کاربر یا پورت SSH فرق دارد، آدرس را از «🗄 سرورها ← ➕"
            " افزودن سرور» بفرست."
        ),
        at=callback.message,
    )


# ---- the draft: name, country, profile, ✅ ------------------------
async def load_draft(state: FSMContext, session: AsyncSession, job_id: str) -> NodeDraft | None:
    """The draft the admin is editing (FSM), or the prepare job's own one — a summary left from
    earlier still works, and becomes the one being edited."""
    data = await state.get_data()
    if data.get("draft_job") == job_id and data.get("draft"):
        return NodeDraft.load(data["draft"])
    job = await OpsJobRepository(session).get(job_id)
    if job is None or job.kind != JobKind.node_prepare or job.status != OpsJobStatus.ok:
        return None
    draft = NodeDraft.load((job.result or {})["draft"])
    await state.update_data(draft_job=job_id, draft=draft.dump())
    return draft


async def show_draft(
    console: Console,
    buttons: ButtonOverrides,
    job_id: str,
    draft: NodeDraft,
    *,
    notice: str = "",
    at: object = None,
) -> None:
    screen = ops_view.draft_screen(job_id, draft, lang=console.lang, buttons=buttons, notice=notice)
    await console.show(*screen, at=at)


def _job_id(data: str | None, prefix: str) -> str:
    return (data or "").removeprefix(prefix).split(":", 1)[0]


async def _draft_or_gone(
    callback: CallbackQuery,
    state: FSMContext,
    session: AsyncSession,
    console: Console,
    buttons: ButtonOverrides,
    prefix: str,
) -> tuple[str, NodeDraft] | None:
    job_id = _job_id(callback.data, prefix)
    draft = await load_draft(state, session, job_id)
    if draft is None:
        await console.show(
            *ops_view.unknown_job(lang=console.lang, buttons=buttons), at=callback.message
        )
        return None
    return job_id, draft


@router.callback_query(F.data.startswith(cb.OPS_DRAFT_GO))
async def draft_go(
    callback: CallbackQuery,
    state: FSMContext,
    console: Console,
    session: AsyncSession,
    redis: Redis,
    arq: ArqRedis | None,
    user: User,
    buttons: ButtonOverrides,
) -> None:
    await callback.answer()
    got = await _draft_or_gone(callback, state, session, console, buttons, cb.OPS_DRAFT_GO)
    if got is None:
        return
    job_id, draft = got
    if not draft.ready:
        await show_draft(console, buttons, job_id, draft, at=callback.message)
        return
    if not await vault_ready(console, buttons, callback.message):
        return
    server = await OpsServerRepository(session).get(draft.server_id)
    if server is None:
        await console.show(
            *ops_view.unknown_job(lang=console.lang, buttons=buttons), at=callback.message
        )
        return
    if not server.key_ok:
        await ask_password(
            console,
            state,
            buttons,
            login=server.address,
            purpose=JobKind.node_install,
            data={"draft": draft.dump()},
            why="کلید ربات این سرور را باز نمی‌کند؛ برای نصب یک بار دیگر رمز لازم است.",
            at=callback.message,
        )
        return
    await state.clear()
    await start_job(
        console,
        session,
        redis,
        arq,
        user,
        buttons,
        kind=JobKind.node_install,
        params={"draft": draft.dump()},
        at=callback.message,
    )


@router.callback_query(F.data.startswith(cb.OPS_DRAFT_NAME))
async def draft_name(
    callback: CallbackQuery,
    state: FSMContext,
    console: Console,
    session: AsyncSession,
    buttons: ButtonOverrides,
) -> None:
    await callback.answer()
    got = await _draft_or_gone(callback, state, session, console, buttons, cb.OPS_DRAFT_NAME)
    if got is None:
        return
    job_id, draft = got
    await state.set_state(OpsFlow.name)
    screen = ops_view.name_prompt(job_id, draft, lang=console.lang, buttons=buttons)
    await console.show(*screen, at=callback.message)


@router.message(StateFilter(OpsFlow.name))
async def name_typed(
    message: Message, state: FSMContext, console: Console, buttons: ButtonOverrides
) -> None:
    await console.consume(message)
    data = await state.get_data()
    job_id, draft = str(data.get("draft_job", "")), NodeDraft.load(data["draft"])
    problem = draft.rename(message.text or "")
    if problem:
        screen = ops_view.name_prompt(
            job_id, draft, problem=problem, lang=console.lang, buttons=buttons
        )
        await console.show(*screen)
        return
    await state.set_state(None)
    await state.update_data(draft=draft.dump())
    await show_draft(console, buttons, job_id, draft, notice="✏️ نام عوض شد")


@router.callback_query(F.data.startswith(cb.OPS_DRAFT_COUNTRY))
async def draft_country(
    callback: CallbackQuery,
    state: FSMContext,
    console: Console,
    session: AsyncSession,
    buttons: ButtonOverrides,
) -> None:
    await callback.answer()
    got = await _draft_or_gone(callback, state, session, console, buttons, cb.OPS_DRAFT_COUNTRY)
    if got is None:
        return
    job_id, draft = got
    await state.set_state(OpsFlow.country)
    screen = ops_view.country_prompt(job_id, draft, lang=console.lang, buttons=buttons)
    await console.show(*screen, at=callback.message)


@router.message(StateFilter(OpsFlow.country))
async def country_typed(
    message: Message, state: FSMContext, console: Console, buttons: ButtonOverrides
) -> None:
    await console.consume(message)
    data = await state.get_data()
    job_id, draft = str(data.get("draft_job", "")), NodeDraft.load(data["draft"])
    code = country_code(message.text or "")
    if code is None:
        screen = ops_view.country_prompt(
            job_id,
            draft,
            problem="این کشور شناخته نشد؛ کد دوحرفی‌اش را بفرست (مثلاً DE).",
            lang=console.lang,
            buttons=buttons,
        )
        await console.show(*screen)
        return
    draft.set_country(code)
    await state.set_state(None)
    await state.update_data(draft=draft.dump())
    await show_draft(console, buttons, job_id, draft, notice=f"🌍 کشور: {ops_view.place(code)}")


@router.callback_query(F.data.startswith(cb.OPS_DRAFT_PROFILES))
async def draft_profiles(
    callback: CallbackQuery,
    state: FSMContext,
    console: Console,
    session: AsyncSession,
    buttons: ButtonOverrides,
) -> None:
    await callback.answer()
    got = await _draft_or_gone(callback, state, session, console, buttons, cb.OPS_DRAFT_PROFILES)
    if got is None:
        return
    job_id, draft = got
    screen = ops_view.profiles_screen(job_id, draft, lang=console.lang, buttons=buttons)
    await console.show(*screen, at=callback.message)


@router.callback_query(F.data.startswith(cb.OPS_DRAFT_PICK))
async def draft_pick(
    callback: CallbackQuery,
    state: FSMContext,
    console: Console,
    session: AsyncSession,
    buttons: ButtonOverrides,
) -> None:
    await callback.answer()
    got = await _draft_or_gone(callback, state, session, console, buttons, cb.OPS_DRAFT_PICK)
    if got is None:
        return
    job_id, draft = got
    index = (callback.data or "").rsplit(":", 1)[-1]
    if index.isdigit() and int(index) < len(draft.profiles):
        draft.choose_profile(draft.profiles[int(index)].uuid)
        await state.update_data(draft=draft.dump())
    notice = f"🧩 پروفایل: {esc(draft.profile.name)}" if draft.profile else ""
    await show_draft(console, buttons, job_id, draft, notice=notice, at=callback.message)


@router.callback_query(F.data.startswith(cb.OPS_DRAFT_BACK))
async def draft_back(
    callback: CallbackQuery,
    state: FSMContext,
    console: Console,
    session: AsyncSession,
    buttons: ButtonOverrides,
) -> None:
    await callback.answer()
    got = await _draft_or_gone(callback, state, session, console, buttons, cb.OPS_DRAFT_BACK)
    if got is None:
        return
    job_id, draft = got
    await state.set_state(None)
    await show_draft(console, buttons, job_id, draft, at=callback.message)


# ---- a job's screen, its log, again, undo ------------------------
async def _job(session: AsyncSession, data: str | None, prefix: str) -> OpsJob | None:
    return await OpsJobRepository(session).get(_job_id(data, prefix))


async def _server_of(session: AsyncSession, job: OpsJob) -> OpsServer | None:
    p = job.params or {}
    sid = p.get("server_id") or (p.get("draft") or {}).get("server_id")
    sid = sid or (job.result or {}).get("server_id")
    return await OpsServerRepository(session).get(int(sid)) if sid is not None else None


@router.callback_query(F.data.startswith(cb.OPS_JOB))
async def job_again_shown(
    callback: CallbackQuery,
    console: Console,
    session: AsyncSession,
    buttons: ButtonOverrides,
) -> None:
    await callback.answer()
    job = await _job(session, callback.data, cb.OPS_JOB)
    if job is None:
        screen = ops_view.unknown_job(lang=console.lang, buttons=buttons)
    else:
        server = await _server_of(session, job)
        screen = ops_view.job_screen(job, server=server, lang=console.lang, buttons=buttons)
    await console.show(*screen, at=callback.message)


@router.callback_query(F.data.startswith(cb.OPS_JOB_LOG))
async def job_log(callback: CallbackQuery, bot: Bot, session: AsyncSession) -> None:
    job = await _job(session, callback.data, cb.OPS_JOB_LOG)
    if job is None or callback.message is None:
        await callback.answer("این کار پیدا نشد", show_alert=True)
        return
    await callback.answer()
    name = f"gozar-{job.kind}-{job.id}.txt"
    await bot.send_document(
        callback.message.chat.id,
        BufferedInputFile(ops_view.log_text(job).encode(), filename=name),
        caption=f"📄 لاگ {ops_view.TITLES.get(job.kind, job.kind)}",
    )


@router.callback_query(F.data.startswith(cb.OPS_JOB_UNDO))
async def job_undo(
    callback: CallbackQuery,
    console: Console,
    session: AsyncSession,
    redis: Redis,
    arq: ArqRedis | None,
    user: User,
    buttons: ButtonOverrides,
) -> None:
    await callback.answer()
    job = await _job(session, callback.data, cb.OPS_JOB_UNDO)
    if job is None or job.kind != JobKind.node_install:
        await console.show(
            *ops_view.unknown_job(lang=console.lang, buttons=buttons), at=callback.message
        )
        return
    await start_job(
        console,
        session,
        redis,
        arq,
        user,
        buttons,
        kind=JobKind.node_undo,
        params={"install_job": job.id},
        at=callback.message,
    )


@router.callback_query(F.data.startswith(cb.OPS_JOB_RETRY))
async def job_retry(
    callback: CallbackQuery,
    state: FSMContext,
    console: Console,
    session: AsyncSession,
    redis: Redis,
    arq: ArqRedis | None,
    user: User,
    buttons: ButtonOverrides,
) -> None:
    """The same job again: with the bot's key where it opens the server, else the password first.
    A failed install starts over from its check (a half-done one is found and offered again)."""
    await callback.answer()
    job = await _job(session, callback.data, cb.OPS_JOB_RETRY)
    if job is None:
        await console.show(
            *ops_view.unknown_job(lang=console.lang, buttons=buttons), at=callback.message
        )
        return
    if job.kind != JobKind.panel_check and not await vault_ready(
        console, buttons, callback.message
    ):
        return
    at = callback.message
    p = dict(job.params or {})
    servers = OpsServerRepository(session)
    server = await _server_of(session, job)
    if job.kind in (JobKind.node_prepare, JobKind.node_install):
        if server is None and "host" in p:
            server = await servers.find(str(p["host"]), int(p["port"]), str(p["username"]))
        if server is not None:
            await prepare_server(console, session, redis, arq, user, state, buttons, server, at=at)
            return
        target = Target(str(p["host"]), int(p["port"]), str(p["username"]))
        await ask_password(
            console,
            state,
            buttons,
            login=target.text,
            purpose=JobKind.node_prepare,
            data={"target": target.params()},
            at=at,
        )
        return
    if job.kind == JobKind.server_add or (
        job.kind in (JobKind.server_test, JobKind.server_forget)
        and server is not None
        and not server.key_ok
    ):
        target = Target.of(server) if server else Target(p["host"], p["port"], p["username"])
        await ask_password(
            console,
            state,
            buttons,
            login=target.text,
            purpose=JobKind.server_add,
            data={"target": target.params()},
            back=cb.OPS_SERVERS,
            at=at,
        )
        return
    await start_job(console, session, redis, arq, user, buttons, kind=job.kind, params=p, at=at)


@router.callback_query(F.data == cb.OPS_TOKEN)
async def token_check(
    callback: CallbackQuery,
    console: Console,
    session: AsyncSession,
    redis: Redis,
    arq: ArqRedis | None,
    user: User,
    buttons: ButtonOverrides,
) -> None:
    await callback.answer()
    await start_job(
        console,
        session,
        redis,
        arq,
        user,
        buttons,
        kind=JobKind.panel_check,
        params={},
        at=callback.message,
    )
