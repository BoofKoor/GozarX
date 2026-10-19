"""The 🖥 nodes and 🗄 servers screens — drawn by the handlers AND by the worker, so nothing here
touches Telegram, the database or a handler: data in, ``(Doc, keyboard)`` out.

A job's screen is drawn from its ``ops_jobs`` row alone (``job_screen``), so the worker's last
picture and a handler's later redraw are the same picture. Every value that came from a server, the
panel or the admin is escaped here; the copy is Persian only, like every operations screen.
"""

from __future__ import annotations

import time
from collections.abc import Sequence
from datetime import datetime
from typing import Any

from aiogram.types import InlineKeyboardMarkup

from gozar.bot import callbacks as cb
from gozar.db.models.enums import Language
from gozar.db.models.ops import OpsJob, OpsJobStatus, OpsServer
from gozar.ops.geo import country_name, flag_of, known
from gozar.ops.report import FAIL, ICONS, PENDING, RUNNING, Reporter
from gozar.remnawave.ops import NodeInfo
from gozar.services.node_draft import NodeDraft
from gozar.services.ops import SECRET_TTL, JobKind, fingerprint
from gozar.services.ops_jobs import install_left_something
from gozar.ui.buttons import ButtonOverrides, ButtonSpec, render_rows
from gozar.ui.fmt import ago, digits, esc, num, when
from gozar.ui.rich import Doc, copy

FA = Language.fa
Screen = tuple[Doc, InlineKeyboardMarkup]
Cell = tuple[str, str] | tuple[str, str, str | None]

#: Rows of the nodes list that get their own "🔗 SSH" button (the rest are still in the table).
SSH_BUTTONS = 8
#: Saved servers offered as buttons on the "➕ node" prompt and the servers list.
SERVER_BUTTONS = 12
#: What a failed job keeps of its log (the last lines; the file the 📄 button sends).
LOG_LINES = 400

TITLES = {
    JobKind.node_prepare: "🖥 نود جدید",
    JobKind.node_install: "🖥 نصب نود",
    JobKind.node_undo: "🧹 برگرداندن نصب",
    JobKind.server_add: "🗄 ذخیرهٔ سرور",
    JobKind.server_test: "🔌 تست اتصال",
    JobKind.server_forget: "🗑 فراموش کردن سرور",
    JobKind.panel_check: "🔑 توکن پنل",
}


def keyboard(
    rows: Sequence[Sequence[Cell]],
    *,
    lang: Language = FA,
    back: str | None = cb.ADMIN_MENU,
    buttons: ButtonOverrides | None = None,
) -> InlineKeyboardMarkup:
    """``(label, callback data[, style])`` cells, then the catalogue's «🔙 admin menu» (its label
    stays operator-editable) pointing at ``back``."""
    structure = [
        [
            ButtonSpec(label=c[0], callback_data=c[1], style=c[2] if len(c) > 2 else None)
            for c in row
        ]
        for row in rows
        if row
    ]
    if back is not None:
        structure.append([ButtonSpec(key="admin_back", callback_data=back)])
    return render_rows(lang, structure, buttons)


def _pairs(cells: list[Cell]) -> list[list[Cell]]:
    return [cells[i : i + 2] for i in range(0, len(cells), 2)]


def place(code: str | None) -> str:
    """«🇩🇪 آلمان (DE)» — or «نامشخص» for an unknown country."""
    if not known(code):
        return "🏳️ نامشخص"
    return f"{flag_of(code)} {esc(country_name(code))} ({esc(str(code).upper())})"


def server_name(server: OpsServer) -> str:
    flag = flag_of(server.country)
    return f"{flag} {esc(server.label)}" if flag else esc(server.label)


def _mb(value: object) -> str:
    try:
        mb = int(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return "—"
    if mb <= 0:
        return "—"
    return digits(f"{mb / 1024:.1f} GB" if mb >= 1024 else f"{mb} MB", FA)


# ---- progress ------------------------
def step_rows(rep: Reporter) -> list[dict[str, Any]]:
    """The reporter's steps as plain data (kept on the job row, so a redraw shows them too)."""
    out = []
    for s in rep.steps:
        el = s.elapsed()
        out.append(
            {
                "key": s.key,
                "title": s.title,
                "status": s.status,
                "note": s.note,
                "detail": s.detail[-3000:],
                "secs": int(el) if el is not None else None,
            }
        )
    return out


def _clock(seconds: float) -> str:
    m, s = divmod(int(seconds), 60)
    return digits(f"{m:02d}:{s:02d}", FA)


def steps_doc(steps: list[dict[str, Any]], doc: Doc | None = None) -> Doc:
    doc = doc if doc is not None else Doc()
    lines = []
    for s in steps:
        line = f"{ICONS.get(s['status'], '•')} {esc(s['title'])}"
        if s["status"] == RUNNING and (s.get("secs") or 0) >= 3:
            line += f" … {digits(str(s['secs']), FA)}ث"
        if s.get("note"):
            line += f" — {esc(s['note'])}"
        lines.append(line)
    doc.lines(lines)
    failed = next((s for s in steps if s["status"] == FAIL and s.get("detail")), None)
    if failed:
        doc.details("🔎 جزئیات خطا", Doc().pre(failed["detail"]))
    return doc


def progress_doc(rep: Reporter, started: float) -> Doc:
    """A job while it runs: the plan, each step's state, the time so far."""
    doc = Doc().h(esc(rep.header or "⏳"), 3)
    steps_doc(step_rows(rep), doc)
    doc.footer(f"⏳ در حال انجام • ⏱ {_clock(time.monotonic() - started)}")
    return doc


def queued_screen(title: str, *, lang: Language = FA, buttons: ButtonOverrides | None = None):
    doc = Doc().h(esc(title), 3).p("⏳ در صف اجرا… همین پیام مرحله‌به‌مرحله به‌روز می‌شود.")
    return doc, keyboard([], lang=lang, back=None, buttons=buttons)


# ---- a finished (or interrupted) job ------------------------
def job_screen(
    job: OpsJob,
    *,
    server: OpsServer | None = None,
    lang: Language = FA,
    buttons: ButtonOverrides | None = None,
) -> Screen:
    """The screen a job leaves behind. ``server``: the saved server it was about, when one is."""
    result = job.result or {}
    steps = result.get("steps") or []
    if job.status in (OpsJobStatus.queued, OpsJobStatus.running):
        doc = Doc().h(esc(TITLES.get(job.kind, "⏳")), 3)
        if steps:
            steps_doc(steps, doc)
        doc.p("⏳ این کار هنوز در حال انجام است؛ پیامش مرحله‌به‌مرحله به‌روز می‌شود.")
        return doc, keyboard([[("🔄 تازه‌سازی", cb.OPS_JOB + job.id)]], lang=lang, buttons=buttons)
    if job.status == OpsJobStatus.ok:
        return _ok_screen(job, result, server, lang, buttons)
    return _failed_screen(job, result, server, lang, buttons)


def _ok_screen(
    job: OpsJob,
    result: dict[str, Any],
    server: OpsServer | None,
    lang: Language,
    buttons: ButtonOverrides | None,
) -> Screen:
    steps = result.get("steps") or []
    if job.kind == JobKind.node_prepare:
        return draft_screen(job.id, NodeDraft.load(result["draft"]), lang=lang, buttons=buttons)
    if job.kind == JobKind.node_install:
        return _installed(job, result, lang, buttons)
    if job.kind == JobKind.node_undo:
        doc = Doc().h("🧹 نصب برگردانده شد", 3)
        steps_doc(steps, doc)
        left = result.get("left") or []
        if left:
            doc.p("⚠️ این‌ها برنگشت و باید دستی پاک شوند:").items([esc(x) for x in left])
        return doc, keyboard([[("🖥 نودها", cb.OPS_NODES)]], lang=lang, buttons=buttons)
    if job.kind in (JobKind.server_add, JobKind.server_test) and server is not None:
        test = result if job.kind == JobKind.server_test else None
        doc, markup = server_screen(server, test=test, lang=lang, buttons=buttons)
        head = Doc()
        if job.kind == JobKind.server_add:
            head.quote("✅ سرور ذخیره شد" + ("" if server.key_ok else " — ولی کلید ربات کار نکرد"))
        else:
            head.quote("✅ اتصال برقرار است")
        return head.extend(doc), markup
    if job.kind == JobKind.server_forget:
        doc = Doc().h(f"🗑 «{esc(str(result.get('label', '')))}» فراموش شد", 3)
        doc.p(
            "کلید ربات از ‎~/.ssh/authorized_keys سرور برداشته شد."
            if result.get("removed")
            else "کلید ربات روی سرور نبود."
        )
        doc.p("اگر این سرور نود است، نودش در پنل سر جایش می‌ماند.")
        return doc, keyboard([[("🗄 سرورها", cb.OPS_SERVERS)]], lang=lang, buttons=buttons)
    if job.kind == JobKind.panel_check:
        return token_screen(result, lang=lang, buttons=buttons)
    doc = Doc().h(esc(TITLES.get(job.kind, "✅")), 3)
    steps_doc(steps, doc)
    return doc, keyboard([[("🖥 نودها", cb.OPS_NODES)]], lang=lang, buttons=buttons)


def _installed(
    job: OpsJob, result: dict[str, Any], lang: Language, buttons: ButtonOverrides | None
) -> Screen:
    plan = result.get("plan") or {}
    n = result.get("node") or {}
    ups = result.get("inbounds_up") or []
    up = sum(1 for _port, ok in ups if ok)
    doc = Doc().h(f"✅ نود «{esc(str(plan.get('name', '')))}» به پنل اضافه شد", 2)
    doc.kv(
        [
            ("🌐 آدرس", f"<code>{esc(str(plan.get('address', '')))}:{plan.get('port', '')}</code>"),
            ("🌍 کشور", place(plan.get("country"))),
            ("🧩 پروفایل", esc(str(plan.get("profile_name", "")))),
            ("🔌 اینباندها", digits(f"{up} از {len(ups)} بالا", FA)),
            ("⚙️ Xray", esc(str(n.get("xray") or "—"))),
            ("📦 نسخهٔ نود", esc(str(n.get("version") or "—"))),
        ]
    )
    doc.quote(
        "کاربرها از راه Hostها به نود می‌رسند: اگر در پنل Hostی با آدرس این سرور نیست، یکی بساز."
    )
    doc.details("مراحل", steps_doc(result.get("steps") or []))
    return doc, keyboard([[("🖥 نودها", cb.OPS_NODES)]], lang=lang, buttons=buttons)


def _failed_screen(
    job: OpsJob,
    result: dict[str, Any],
    server: OpsServer | None,
    lang: Language,
    buttons: ButtonOverrides | None,
) -> Screen:
    steps = result.get("steps") or []
    interrupted = job.status == OpsJobStatus.interrupted
    doc = Doc().h(esc(TITLES.get(job.kind, "❌")) + (" — نیمه‌کاره ماند" if interrupted else ""), 3)
    if interrupted:
        doc.quote("⚠️ ربات وسط این کار ری‌استارت شد و کار ادامه پیدا نکرد.")
    elif job.error:
        doc.quote("❌ " + esc(job.error))
    steps_doc(steps, doc)
    code = result.get("code")
    rows: list[list[Cell]] = []
    server_id = _server_id(job, result)
    if code == "hostkey" and server_id is not None:
        doc.p(
            "اگر سرور را از نو نصب کرده‌ای یا SSH آن عوض شده، کلید تازه را قبول کن؛ وگرنه کسی ممکن"
            " است خودش را جای سرور جا زده باشد و نباید وصل شد."
        )
        rows.append([("♻️ قبول کلید تازهٔ سرور", cb.OPS_SERVER_TRUST + str(server_id), "danger")])
    if job.kind == JobKind.node_install and install_left_something(result.get("plan")):
        doc.p("بخشی از نصب انجام شده؛ با «🧹 برگرداندن» هر چه انجام شده پاک می‌شود.")
        rows.append([("🧹 برگرداندن", cb.OPS_JOB_UNDO + job.id, "danger")])
    if job.kind == JobKind.server_forget and server_id is not None:
        rows.append([("🗑 فراموش کن بدون برداشتن کلید", cb.OPS_SERVER_DROP + str(server_id))])
    retry = "🔑 دوباره با رمز" if code == "auth" else "🔁 دوباره"
    tail: list[Cell] = [(retry, cb.OPS_JOB_RETRY + job.id)]
    if result.get("log"):
        tail.append(("📄 لاگ", cb.OPS_JOB_LOG + job.id))
    rows.append(tail)
    back = (
        cb.OPS_SERVERS
        if job.kind in (JobKind.server_add, JobKind.server_test, JobKind.server_forget)
        else cb.OPS_NODES
    )
    rows.append([("🔙 " + ("سرورها" if back == cb.OPS_SERVERS else "نودها"), back)])
    return doc, keyboard(rows, lang=lang, buttons=buttons)


def _server_id(job: OpsJob, result: dict[str, Any]) -> int | None:
    p = job.params or {}
    if "server_id" in p:
        return int(p["server_id"])
    if "draft" in p:
        return int(p["draft"]["server_id"])
    if result.get("server_id") is not None:
        return int(result["server_id"])
    return None


# ---- the draft: a node waiting for ✅ ------------------------
def draft_screen(
    job_id: str,
    draft: NodeDraft,
    *,
    lang: Language = FA,
    buttons: ButtonOverrides | None = None,
    notice: str = "",
) -> Screen:
    """The summary before ✅ (``notice``: HTML — what the last change did)."""
    f = draft.facts
    profile = draft.profile
    doc = Doc().h(f"🖥 نود جدید: {esc(draft.name)}", 2)
    if notice:
        doc.quote(notice)
    login = f"<code>{esc(draft.login)}</code> " + (
        "🔑 با کلید ربات" if draft.key_ok else "⚠️ کلید ربات کار نکرد؛ نصب دوباره رمز می‌خواهد"
    )
    docker = esc(str(f.get("docker") or "")) or "نصب نیست؛ نصب می‌شود"
    doc.kv(
        [
            ("🔐 ورود", login),
            ("🌐 آدرس نود", f"<code>{esc(draft.address)}:{draft.node_port}</code>"),
            ("🌍 کشور", place(draft.country)),
            (
                "🧩 پروفایل",
                f"{esc(profile.name)} • {digits(str(profile.inbounds), FA)} اینباند"
                + (f" — {esc(draft.profile_why)}" if draft.profile_why else "")
                if profile
                else "—",
            ),
            ("🐧 سیستم", " • ".join(esc(str(x)) for x in (f.get("os"), f.get("arch")) if x)),
            ("💾 رم / دیسک آزاد", f"{_mb(f.get('mem_mb'))} / {_mb(f.get('disk_mb'))}"),
            ("🐳 Docker", docker),
            ("🧱 ufw", "روشن — پورت‌های لازم باز می‌شوند" if f.get("ufw") else "خاموش"),
            ("🏢 ارائه‌دهنده", esc(str(f["isp"]))) if f.get("isp") else None,
        ]
    )
    if draft.existing:
        doc.quote(
            f"♻️ روی سرور {esc(draft.existing)} هست؛ با ✅ اول متوقف و بکاپ می‌شود، بعد نود تازه"
            " نصب می‌شود."
        )
    if draft.sudo_kept:
        doc.quote(
            "🔒 sudo این کاربر رمز می‌خواهد، پس رمزش رمزنگاری‌شده کنار سرور نگه داشته شد. با کاربر"
            " root یا sudo بدون رمز، ربات هیچ رمزی نگه نمی‌دارد."
        )
    problems = draft.problems
    if problems:
        doc.p("⛔ تا این‌ها درست نشوند نصب شروع نمی‌شود:").items([esc(x) for x in problems])
    if draft.warnings:
        doc.p("⚠️ بدان:").items([esc(x) for x in draft.warnings])
    rows: list[list[Cell]] = []
    if not problems:
        rows.append([("✅ نصب نود", cb.OPS_DRAFT_GO + job_id, "success")])
    edit: list[Cell] = [
        ("✏️ نام", cb.OPS_DRAFT_NAME + job_id),
        ("🌍 کشور", cb.OPS_DRAFT_COUNTRY + job_id),
    ]
    if len(draft.profiles) > 1:
        edit.append(("🧩 پروفایل", cb.OPS_DRAFT_PROFILES + job_id))
    rows.append(edit)
    rows.append(
        [("🔁 بررسی دوباره", cb.OPS_SERVER_NODE + str(draft.server_id)), ("❌ لغو", cb.OPS_NODES)]
    )
    doc.footer("با ✅ نصب شروع می‌شود و هر مرحله‌اش همین‌جا نشان داده می‌شود.")
    return doc, keyboard(rows, lang=lang, back=None, buttons=buttons)


def profiles_screen(
    job_id: str, draft: NodeDraft, *, lang: Language = FA, buttons: ButtonOverrides | None = None
) -> Screen:
    doc = Doc().h("🧩 کانفیگ پروفایل نود", 3)
    doc.p("نود همهٔ اینباندهای پروفایلی را که انتخاب کنی اجرا می‌کند:")
    doc.table(
        ["پروفایل", "اینباند", "نود", "پورت‌ها"],
        [
            [
                ("✓ " if p.uuid == draft.profile_uuid else "") + esc(p.name),
                digits(str(p.inbounds), FA),
                digits(str(p.nodes), FA),
                esc(", ".join(f"{port}/{proto}" for port, proto in p.ports[:6]))
                + (" …" if len(p.ports) > 6 else ""),
            ]
            for p in draft.profiles
        ],
    )
    cells: list[Cell] = [
        (
            ("✓ " if p.uuid == draft.profile_uuid else "") + p.name,
            f"{cb.OPS_DRAFT_PICK}{job_id}:{i}",
        )
        for i, p in enumerate(draft.profiles)
    ]
    rows = _pairs(cells) + [[("🔙 خلاصه", cb.OPS_DRAFT_BACK + job_id)]]
    return doc, keyboard(rows, lang=lang, back=None, buttons=buttons)


def name_prompt(
    job_id: str,
    draft: NodeDraft,
    *,
    problem: str = "",
    lang: Language = FA,
    buttons: ButtonOverrides | None = None,
) -> Screen:
    doc = Doc().h("✏️ نام نود", 3)
    doc.p(f"نام فعلی: {esc(draft.name)}")
    doc.p("نام تازه را بفرست (۳ تا ۳۰ کاراکتر). قرار نام‌ها: پرچم و بعد نام کشور، مثل «🇩🇪 آلمان».")
    if problem:
        doc.quote("⚠️ " + esc(problem))
    return doc, keyboard(
        [[("🔙 خلاصه", cb.OPS_DRAFT_BACK + job_id)]], lang=lang, back=None, buttons=buttons
    )


def country_prompt(
    job_id: str,
    draft: NodeDraft,
    *,
    problem: str = "",
    lang: Language = FA,
    buttons: ButtonOverrides | None = None,
) -> Screen:
    doc = Doc().h("🌍 کشور نود", 3)
    doc.p(f"الان: {place(draft.country)}")
    doc.p("کد دوحرفی کشور (DE) یا نامش (آلمان / Germany) یا پرچمش (🇩🇪) را بفرست.")
    if draft.name_auto:
        doc.p("نام پیشنهادی نود هم با کشور عوض می‌شود.")
    if problem:
        doc.quote("⚠️ " + esc(problem))
    return doc, keyboard(
        [[("🔙 خلاصه", cb.OPS_DRAFT_BACK + job_id)]], lang=lang, back=None, buttons=buttons
    )


# ---- 🖥 the panel's nodes ------------------------
def _node_state(n: NodeInfo) -> str:
    if n.is_disabled:
        return "⏸ خاموش"
    if n.is_connected:
        return "🟢 وصل"
    if n.is_connecting:
        return "🟡 در حال اتصال"
    return "🔴 قطع"


def nodes_screen(
    nodes: list[NodeInfo] | None,
    saved: dict[str, OpsServer],
    *,
    error: str = "",
    lang: Language = FA,
    buttons: ButtonOverrides | None = None,
) -> Screen:
    """The panel's nodes, each with whether the bot can SSH into its server (``saved``: address →
    saved server)."""
    doc = Doc().h("🖥 نودهای پنل", 2)
    rows: list[list[Cell]] = [[("➕ افزودن نود", cb.OPS_NODES_ADD, "primary")]]
    if nodes is None:
        doc.quote("⚠️ " + esc(error or "پنل جواب نداد"))
    elif not nodes:
        doc.p("هنوز نودی در پنل نیست. با «➕ افزودن نود» اولین سرور را نود کن.")
    else:
        online = sum(n.users_online or 0 for n in nodes)
        up = sum(1 for n in nodes if n.is_connected)
        doc.p(digits(f"{up} از {len(nodes)} نود وصل • {online} کاربر آنلاین", FA))
        table = []
        for n in nodes:
            srv = saved.get(n.address)
            ssh = "—" if srv is None else ("🔑" if srv.key_ok else "⚠️")
            flag = flag_of(n.country)
            table.append(
                [
                    f"{flag} {esc(n.name)}" if flag and flag not in n.name else esc(n.name),
                    f"<code>{esc(n.address)}</code>",
                    _node_state(n),
                    num(n.users_online, FA),
                    ssh,
                ]
            )
        doc.table(["نود", "آدرس", "وضعیت", "آنلاین", "SSH"], table, striped=True)
        bad = [n for n in nodes if not n.is_connected and not n.is_disabled and n.last_status]
        if bad:
            body = Doc().items(
                [f"{esc(n.name)}: {esc((n.last_status or '')[:200])}" for n in bad[:8]]
            )
            doc.details("🔴 پیام آخر نودهای قطع", body)
        unlinked = [n for n in nodes if n.address not in saved][:SSH_BUTTONS]
        if unlinked:
            doc.footer(
                "🔑 یعنی ربات با کلید خودش به آن سرور وصل می‌شود. «🔗» یکی را به ربات وصل می‌کند."
            )
            rows += _pairs([(f"🔗 {n.name}", cb.OPS_NODE_SSH + n.uuid) for n in unlinked])
        else:
            doc.footer("🔑 یعنی ربات با کلید خودش به آن سرور وصل می‌شود.")
    rows.append([("🗄 سرورها", cb.OPS_SERVERS), ("🔑 توکن پنل", cb.OPS_TOKEN)])
    rows.append([("🔄 تازه‌سازی", cb.OPS_NODES)])
    return doc, keyboard(rows, lang=lang, buttons=buttons)


# ---- 🗄 saved servers ------------------------
def servers_screen(
    servers: list[OpsServer], *, lang: Language = FA, buttons: ButtonOverrides | None = None
) -> Screen:
    doc = Doc().h("🗄 سرورهای ذخیره‌شده", 2)
    if not servers:
        doc.p(
            "هنوز سروری ذخیره نشده. هر سروری که ربات یک بار با رمز واردش شود (برای نود کردن یا با"
            " «➕ افزودن سرور») این‌جا ذخیره می‌شود و از آن به بعد با کلید ربات باز می‌شود."
        )
    else:
        doc.table(
            ["سرور", "ورود", "کلید", "آخرین ورود"],
            [
                [
                    server_name(s),
                    f"<code>{esc(s.address)}</code>",
                    "✅" if s.key_ok else "⚠️",
                    ago(s.last_login_at, FA),
                ]
                for s in servers
            ],
            striped=True,
        )
        doc.footer("⚠️ یعنی کلید ربات دیگر قبول نمی‌شود و ورود بعدی رمز می‌خواهد.")
    cells: list[Cell] = [
        (f"{flag_of(s.country)} {s.label}".strip(), cb.OPS_SERVER_OPEN + str(s.id))
        for s in servers[:SERVER_BUTTONS]
    ]
    rows = _pairs(cells)
    rows.append([("➕ افزودن سرور", cb.OPS_SERVERS_ADD), ("🖥 نودها", cb.OPS_NODES)])
    return doc, keyboard(rows, lang=lang, buttons=buttons)


def server_screen(
    server: OpsServer,
    *,
    test: dict[str, Any] | None = None,
    lang: Language = FA,
    buttons: ButtonOverrides | None = None,
) -> Screen:
    doc = Doc().h(f"🗄 {server_name(server)}", 2)
    key = "✅ کار می‌کند" if server.key_ok else "⚠️ کار نمی‌کند — ورود بعدی رمز می‌خواهد"
    rows: list[tuple[str, str] | None] = [
        ("🔐 ورود", f"<code>{esc(server.address)}</code> {copy(server.address)}"),
        ("🌐 آی‌پی", f"<code>{esc(server.ip)}</code>")
        if server.ip and server.ip != server.host
        else None,
        ("🌍 کشور", place(server.country)),
        ("🐧 سیستم", esc(server.os)) if server.os else None,
        ("🔑 کلید ربات", key),
        ("🔒 sudo", "رمزش رمزنگاری‌شده نگه داشته شده") if server.sudo_password else None,
        ("🧬 اثر انگشت SSH", f"<code>{esc(fingerprint(server.host_key))}</code>")
        if server.host_key
        else None,
        ("🕓 آخرین ورود", ago(server.last_login_at, FA)),
        ("📅 ذخیره شده", when(server.created_at, FA, "d")),
    ]
    doc.kv(rows)
    if test:
        doc.kv(
            [
                ("💾 رم / دیسک آزاد", f"{_mb(test.get('mem_mb'))} / {_mb(test.get('disk_mb'))}"),
                ("🐳 Docker", esc(str(test.get("docker") or "نصب نیست"))),
                ("🖥 remnanode", esc(str(test.get("remnanode") or "نیست"))),
                ("🗝 کلیدهای SSH کاربر", digits(str(test.get("keys", 0)), FA)),
            ],
            caption="تست الان",
        )
    rows_kb: list[list[Cell]] = [
        [
            ("🔌 تست اتصال", cb.OPS_SERVER_TEST + str(server.id)),
            ("🖥 نود کن", cb.OPS_SERVER_NODE + str(server.id)),
        ],
        [("🗑 فراموش کن", cb.OPS_SERVER_FORGET + str(server.id), "danger")],
        [("🗄 سرورها", cb.OPS_SERVERS)],
    ]
    return doc, keyboard(rows_kb, lang=lang, buttons=buttons)


def forget_confirm(
    server: OpsServer, *, lang: Language = FA, buttons: ButtonOverrides | None = None
) -> Screen:
    doc = Doc().h(f"🗑 «{server_name(server)}» فراموش شود؟", 3)
    doc.p(
        "ربات واردش می‌شود، کلید خودش را از ‎~/.ssh/authorized_keys برمی‌دارد و سرور را از فهرستش"
        " پاک می‌کند. کلیدهای خودت دست نمی‌خورند و اگر این سرور نود است، نودش در پنل می‌ماند."
    )
    rows: list[list[Cell]] = [
        [
            ("🗑 فراموش کن", cb.OPS_SERVER_FORGET_OK + str(server.id), "danger"),
            ("❌ لغو", cb.OPS_SERVER_OPEN + str(server.id)),
        ]
    ]
    return doc, keyboard(rows, lang=lang, back=None, buttons=buttons)


def trust_confirm(
    server: OpsServer, *, lang: Language = FA, buttons: ButtonOverrides | None = None
) -> Screen:
    doc = Doc().h("♻️ قبول کلید تازهٔ SSH", 3)
    doc.p(
        f"کلید SSHی که «{server_name(server)}» نشان می‌دهد با دفعهٔ قبل فرق دارد. اگر سرور را از نو"
        " نصب کرده‌ای عادی است؛ اگر نه، ممکن است کس دیگری خودش را جای سرور جا زده باشد."
    )
    if server.host_key:
        doc.p(f"کلید قبلی: <code>{esc(fingerprint(server.host_key))}</code>")
    doc.p("با تأیید، ورود بعدی کلید تازه را می‌پذیرد و همان را نگه می‌دارد.")
    rows: list[list[Cell]] = [
        [
            ("♻️ قبول", cb.OPS_SERVER_TRUST + f"{server.id}:ok", "danger"),
            ("❌ لغو", cb.OPS_SERVER_OPEN + str(server.id)),
        ]
    ]
    return doc, keyboard(rows, lang=lang, back=None, buttons=buttons)


# ---- 🔑 the panel token ------------------------
def token_screen(
    result: dict[str, Any], *, lang: Language = FA, buttons: ButtonOverrides | None = None
) -> Screen:
    missing = set(result.get("missing") or [])
    doc = Doc().h("🔑 دسترسی‌های توکن پنل", 2)
    groups = [("🖥 افزودن نود", result.get("node") or [])] + [
        (what, scopes) for what, scopes in result.get("features") or []
    ]
    for what, scopes in groups:
        ok = not (set(scopes) & missing)
        doc.h(f"{'✅' if ok else '❌'} {esc(what)}", 4)
        doc.checks([(s not in missing, f"<code>{esc(s)}</code>") for s in scopes])
    if missing:
        doc.quote(
            "در داشبورد پنل (Remnawave Settings ← API Tokens) توکنی با این دسترسی‌ها بساز، جای"
            " PANEL_API_TOKEN در ‎.env بگذار و ربات را ری‌استارت کن. ربات با توکن فعلی کاری را که"
            " دسترسی‌اش را ندارد شروع نمی‌کند."
        )
    else:
        doc.p("توکن همهٔ دسترسی‌های لازم را دارد.")
    rows: list[list[Cell]] = [[("🔄 بررسی دوباره", cb.OPS_TOKEN), ("🖥 نودها", cb.OPS_NODES)]]
    return doc, keyboard(rows, lang=lang, buttons=buttons)


# ---- prompts ------------------------
def address_prompt(
    *,
    for_node: bool,
    servers: list[OpsServer] = (),  # type: ignore[assignment]
    problem: str = "",
    lang: Language = FA,
    buttons: ButtonOverrides | None = None,
) -> Screen:
    doc = Doc().h("➕ افزودن نود" if for_node else "➕ افزودن سرور", 3)
    doc.p("آدرس SSH سرور را بفرست، مثلاً:")
    doc.pre("1.2.3.4\nroot@1.2.3.4:2222\nubuntu@node.example.com")
    doc.p("کاربر پیش‌فرض root و پورت پیش‌فرض ۲۲ است.")
    if problem:
        doc.quote("⚠️ " + esc(problem))
    rows: list[list[Cell]] = []
    if for_node and servers:
        doc.p("یا یکی از سرورهای ذخیره‌شده را انتخاب کن (بدون رمز):")
        rows += _pairs(
            [
                (f"{flag_of(s.country)} {s.label}".strip(), cb.OPS_SERVER_NODE + str(s.id))
                for s in servers[:SERVER_BUTTONS]
            ]
        )
    rows.append([("❌ لغو", cb.OPS_NODES if for_node else cb.OPS_SERVERS)])
    return doc, keyboard(rows, lang=lang, back=None, buttons=buttons)


def password_prompt(
    login: str,
    *,
    why: str = "",
    back: str = cb.OPS_NODES,
    lang: Language = FA,
    buttons: ButtonOverrides | None = None,
) -> Screen:
    doc = Doc().h(f"🔐 رمز {esc(login)}", 3)
    if why:
        doc.quote(esc(why))
    doc.p("رمز ورود این کاربر را بفرست.")
    doc.quote(
        "پیامت همین که خوانده شود از چت پاک می‌شود. رمز فقط یک بار، برای ورود و نصب کلید SSH خود"
        " ربات، به کار می‌رود و هیچ‌جا ذخیره نمی‌شود؛ از دفعهٔ بعد ربات با کلیدش وارد می‌شود. تا "
        + digits(str(SECRET_TTL // 60), FA)
        + " دقیقه بعد از فرستادنش استفاده می‌شود و بعد دیگر نیست."
    )
    return doc, keyboard([[("❌ لغو", back)]], lang=lang, back=None, buttons=buttons)


def vault_missing(*, lang: Language = FA, buttons: ButtonOverrides | None = None) -> Screen:
    doc = Doc().h("🔐 VAULT_KEY تنظیم نشده", 3)
    doc.p(
        "ربات کلید SSH خودش (و رمز sudo، اگر سروری بخواهد) را رمزنگاری‌شده با VAULT_KEY نگه می‌دارد"
        " و این مقدار هنوز در ‎.env نیست. روی سرور ربات این را اجرا کن؛ فقط همین را اضافه می‌کند و"
        " ربات را ری‌استارت می‌کند:"
    )
    doc.pre("cd ~/GozarX && sudo ./install.sh --secrets")
    return doc, keyboard([[("🖥 نودها", cb.OPS_NODES)]], lang=lang, buttons=buttons)


def busy_screen(job: OpsJob, *, lang: Language = FA, buttons: ButtonOverrides | None = None):
    doc = Doc().h("⏳ یک کار SSH در جریان است", 3)
    started = job.started_at or job.created_at
    doc.p(f"{esc(TITLES.get(job.kind, job.kind))} — از {ago(started, FA)}")
    doc.p("تا تمام نشده کار دیگری شروع نمی‌شود؛ پیامش مرحله‌به‌مرحله به‌روز می‌شود.")
    rows: list[list[Cell]] = [[("👀 نشانم بده", cb.OPS_JOB + job.id)]]
    return doc, keyboard(rows, lang=lang, buttons=buttons)


def unknown_job(*, lang: Language = FA, buttons: ButtonOverrides | None = None) -> Screen:
    doc = Doc().h("🤷 این کار پیدا نشد", 3).p("از «🖥 نودها» دوباره شروع کن.")
    return doc, keyboard([[("🖥 نودها", cb.OPS_NODES)]], lang=lang, buttons=buttons)


def log_text(job: OpsJob) -> str:
    """The 📄 file: the job's own steps, then what it ran (secrets already masked)."""
    result = job.result or {}
    head = [
        f"gozar ops job {job.id} — {job.kind} — {job.status}",
        f"created {_iso(job.created_at)} · started {_iso(job.started_at)} · "
        f"finished {_iso(job.finished_at)}",
    ]
    if job.error:
        head.append(f"error: {job.error}")
    steps = [
        f"[{s['status']}] {s['title']}" + (f" — {s['note']}" if s.get("note") else "")
        for s in result.get("steps") or []
    ]
    return "\n".join([*head, "", *steps, "", *(result.get("log") or [])]) + "\n"


def _iso(instant: datetime | None) -> str:
    return instant.isoformat(timespec="seconds") if instant else "—"


__all__ = [
    "LOG_LINES",
    "PENDING",
    "address_prompt",
    "busy_screen",
    "country_prompt",
    "draft_screen",
    "forget_confirm",
    "job_screen",
    "keyboard",
    "log_text",
    "name_prompt",
    "nodes_screen",
    "password_prompt",
    "profiles_screen",
    "progress_doc",
    "queued_screen",
    "server_screen",
    "servers_screen",
    "step_rows",
    "token_screen",
    "trust_confirm",
    "unknown_job",
    "vault_missing",
]
