"""What each console operation does, step by step — run by the worker (``worker/ops.ops_run``).

A body gets the job's row, a session of its own, the panel and a ``Reporter``, and returns the
job's result: plain JSON, no secret, kept on the row and drawn by the console. A step that fails
raises ``RemoteError`` (its message is for the admin); the worker records the failure, the steps
shown so far, and whatever the body left in ``rep.context`` for the console to offer next (an
install's plan, for 🧹 undo).

Every login is one of two: the bot's own key for a saved server (``connect_saved``), or a password
handed over for this job alone (``secret``), used once to install that key. A body never keeps the
password: it lives in the credentials until the key is in, and the worker drops the job's last
reference when the body returns.
"""

from __future__ import annotations

import json
from collections.abc import Awaitable, Callable
from dataclasses import asdict, dataclass
from typing import Any

import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from gozar.db.models.ops import OpsJob, OpsServer
from gozar.db.repositories.ops import OpsJobRepository
from gozar.ops import access, node
from gozar.ops.errors import RemoteError
from gozar.ops.report import Reporter
from gozar.ops.ssh import Server
from gozar.remnawave.ops import NODE_SCOPES, SCOPE_PROBES, OpsPanel
from gozar.services.node_draft import NodeDraft
from gozar.services.ops import JobKind, OpsService, Target


@dataclass
class JobEnv:
    job: OpsJob
    session: AsyncSession
    http: httpx.AsyncClient
    panel: OpsPanel
    rep: Reporter
    secret: str | None = None  # this job's password, when it was given one

    @property
    def ops(self) -> OpsService:
        return OpsService(self.session, self.http)


Body = Callable[[JobEnv], Awaitable[dict[str, Any]]]


# ---- logging in --------------------
async def _server(env: JobEnv, server_id: int) -> OpsServer:
    row = await env.ops.servers.get(server_id)
    if row is None:
        raise RemoteError("این سرور دیگر در ربات ذخیره نیست")
    return row


async def _login(env: JobEnv, *, server: OpsServer | None, target: Target | None) -> tuple:
    """``(server, row, line)``: in with the job's password when it has one (the bot's key goes in
    on the way), else with the bot's key."""
    ops = env.ops
    if server is None and target is not None:
        server = await ops.servers.find(target.host, target.port, target.username)
    if env.secret is not None:
        srv, row, line = await ops.login_new(
            target or Target.of(server), env.secret, debug=env.rep.debug
        )
        return srv, row, line
    if server is None:
        raise RemoteError("برای ورود به این سرور رمز لازم است", code="auth")
    srv = await ops.connect_saved(server, debug=env.rep.debug)
    return srv, server, "🔑 با کلید ربات وصل شدم"


def _sudo_line(srv: Server) -> str:
    if srv.sudo_mode == "password":
        return " • sudo رمز می‌خواهد (رمزش رمزنگاری‌شده نگه داشته شد)"
    if srv.sudo_mode == "nopasswd":
        return " • با sudo"
    return ""


# ---- 🖥 nodes --------------------
async def node_prepare(env: JobEnv) -> dict[str, Any]:
    p = env.job.params
    server = await _server(env, int(p["server_id"])) if "server_id" in p else None
    target = None if server else Target(str(p["host"]), int(p["port"]), str(p["username"]))
    shown = server.address if server else target.text  # type: ignore[union-attr]
    await env.rep.plan(
        [
            ("panel", "دسترسی به پنل"),
            ("login", "ورود به سرور"),
            ("check", "بررسی سرور"),
        ],
        header=f"🖥 نود جدید روی {shown}",
    )
    async with env.rep.stage("panel") as st:
        profiles, nodes = await env.panel.check_access()
        await st.note(f"{len(nodes)} نود • {len(profiles)} کانفیگ پروفایل")
    async with env.rep.stage("login") as st:
        srv, row, line = await _login(env, server=server, target=target)
        await st.note(line + _sudo_line(srv))
    async with srv:
        async with env.rep.stage("check") as st:
            prep = await node.prepare(
                env.panel, env.http, srv, profiles, nodes, debug=env.rep.debug
            )
            row.os = (prep.facts.os_pretty or prep.facts.os_id)[:128]
            await st.note(f"🐧 {row.os or '?'} • {prep.facts.arch} • {prep.geo.label}")
    draft = NodeDraft.from_prep(
        prep,
        server_id=row.id,
        login=row.address,
        key_ok=row.key_ok,
        sudo_kept=bool(row.sudo_password),
    )
    return {"draft": draft.dump()}


async def node_install(env: JobEnv) -> dict[str, Any]:
    draft = NodeDraft.load(env.job.params["draft"])
    server = await _server(env, draft.server_id)
    await env.rep.plan([("login", "ورود به سرور")], header=f"🖥 افزودن نود «{draft.name}» به پنل")
    async with env.rep.stage("login") as st:
        srv, _row, line = await _login(env, server=server, target=None)
        await st.note(line)
    async with srv:
        plan = draft.plan(env.panel.host)
        result = await node.install(env.panel, srv, plan, env.rep, node.image_candidates())
    n = result.node
    return {
        "plan": asdict(plan),
        "node": {
            "uuid": n.uuid,
            "name": n.name,
            "address": n.address,
            "port": n.port,
            "xray": n.xray_version,
            "version": n.node_version,
        }
        if n is not None
        else None,
        "inbounds_up": [[port, up] for port, up in sorted(result.inbounds_up.items())],
    }


def install_left_something(plan: dict[str, Any] | None) -> bool:
    """Did an install that stopped half way change anything 🧹 undo would reverse?"""
    if not plan:
        return False
    return bool(
        plan.get("files_written")
        or plan.get("node_uuid")
        or plan.get("backup_dir")
        or plan.get("ufw_rules")
    )


async def node_undo(env: JobEnv) -> dict[str, Any]:
    install = await OpsJobRepository(env.session).get(str(env.job.params["install_job"]))
    if install is None or install.kind != JobKind.node_install:
        raise RemoteError("نصبی که باید برگردانده شود پیدا نشد")
    draft = NodeDraft.load(install.params["draft"])
    recorded = (install.result or {}).get("plan")
    srv: Server | None = None
    reason = ""
    try:
        srv = await env.ops.connect_saved(await _server(env, draft.server_id), debug=env.rep.debug)
    except RemoteError as e:
        reason = e.message
    try:
        if recorded is None and srv is not None:  # the worker died before it wrote one down
            marker = await srv.read_file(node.MARKER)
            recorded = json.loads(marker) if marker else None
        if not isinstance(recorded, dict):
            raise RemoteError(
                "از این نصب چیزی ثبت نشده که برگردانده شود"
                + (f" (به سرور هم وصل نشدم: {reason})" if reason else "")
            )
        plan = node.NodePlan(
            **{k: v for k, v in recorded.items() if k in node.NodePlan.__dataclass_fields__}
        )
        left = await node.undo(env.panel, srv, plan, env.rep)
    finally:
        if srv is not None:
            await srv.close()
            srv.creds.wipe()
    return {"plan": asdict(plan), "left": left, "unreachable": reason}


# ---- 🗄 servers --------------------
async def server_add(env: JobEnv) -> dict[str, Any]:
    p = env.job.params
    target = Target(str(p["host"]), int(p["port"]), str(p["username"]))
    await env.rep.plan(
        [("login", "ورود و نصب کلید ربات"), ("facts", "بررسی سرور")],
        header=f"🗄 ذخیرهٔ سرور {target.text}",
    )
    async with env.rep.stage("login") as st:
        if env.secret is None:
            raise RemoteError("برای اولین ورود رمز لازم است", code="auth")
        srv, row, line = await env.ops.login_new(target, env.secret, debug=env.rep.debug)
        await st.note(line + _sudo_line(srv))
    async with srv:
        async with env.rep.stage("facts") as st:
            facts = await node.gather(srv)
            row.os = (facts.os_pretty or facts.os_id)[:128]
            await st.note(f"🐧 {row.os or '?'} • {facts.arch}")
    return {"server_id": row.id, "key_ok": row.key_ok}


async def server_test(env: JobEnv) -> dict[str, Any]:
    server = await _server(env, int(env.job.params["server_id"]))
    await env.rep.plan(
        [("login", "ورود با کلید ربات"), ("facts", "بررسی سرور")],
        header=f"🔌 تست اتصال {server.label}",
    )
    async with env.rep.stage("login") as st:
        srv = await env.ops.connect_saved(server, debug=env.rep.debug)
        await st.note(f"وصل شدم • {srv.fingerprint or ''}{_sudo_line(srv)}")
    async with srv:
        async with env.rep.stage("facts") as st:
            facts = await node.gather(srv)
            keys, ours = await access.keys_info(srv, await env.ops.bot_public())
            server.os = (facts.os_pretty or facts.os_id)[:128]
            await st.note(f"🐧 {server.os or '?'} • {facts.arch}")
    container = facts.rn_container.split("|")
    return {
        "server_id": server.id,
        "os": server.os,
        "arch": facts.arch,
        "mem_mb": facts.mem_mb,
        "disk_mb": facts.disk_mb,
        "docker": facts.docker if facts.has_docker else "",
        "remnanode": container[1] if len(container) > 1 else "",
        "keys": keys,
        "our_key": ours,
    }


async def server_forget(env: JobEnv) -> dict[str, Any]:
    server = await _server(env, int(env.job.params["server_id"]))
    label = server.label
    await env.rep.plan(
        [("login", "ورود با کلید ربات"), ("key", "برداشتن کلید ربات از سرور"), ("forget", "حذف")],
        header=f"🗑 فراموش کردن {label}",
    )
    async with env.rep.stage("login"):
        srv = await env.ops.connect_saved(server, debug=env.rep.debug)
    async with srv:
        async with env.rep.stage("key") as st:
            removed = await access.remove_key(srv, await env.ops.bot_public())
            await st.note("برداشته شد" if removed else "روی سرور نبود")
    async with env.rep.stage("forget"):
        await env.ops.servers.delete(server)
    return {"label": label, "removed": removed}


# ---- 🔑 the panel token --------------------
async def panel_check(env: JobEnv) -> dict[str, Any]:
    await env.rep.plan([("scopes", "دسترسی‌های توکن پنل")], header="🔑 توکن پنل")
    async with env.rep.stage("scopes") as st:
        missing = await env.panel.scopes_missing()
        await st.note(f"{len(SCOPE_PROBES) - len(missing)} از {len(SCOPE_PROBES)}")
    return {"missing": missing, "node": list(NODE_SCOPES)}


BODIES: dict[str, Body] = {
    JobKind.node_prepare: node_prepare,
    JobKind.node_install: node_install,
    JobKind.node_undo: node_undo,
    JobKind.server_add: server_add,
    JobKind.server_test: server_test,
    JobKind.server_forget: server_forget,
    JobKind.panel_check: panel_check,
}
