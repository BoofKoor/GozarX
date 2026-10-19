"""Every 🖥 nodes / 🗄 servers screen is valid Telegram markup — rich, regular and its keyboard,
plain and with premium icons — including what a server, the panel or the admin typed (escaped)."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from gozar.bot import callbacks as cb
from gozar.bot import ops_view, screens
from gozar.db.models.ops import OpsJob, OpsJobStatus, OpsServer
from gozar.ops.report import FAIL, OK, RUNNING, Reporter
from gozar.remnawave.ops import NodeInfo
from gozar.services.node_draft import NodeDraft, ProfileChoice
from gozar.services.ops import JobKind
from gozar.ui.look import PLAIN, Look
from gozar.ui.validate import check_classic, check_keyboard, check_rich

NOW = datetime(2026, 10, 19, 12, 0, tzinfo=UTC)
HOSTKEY = "ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIOMqqnkVzrm0SdG6UOoqKLsabgH5C9okWi0dh2l9GKJl"


def _server(**kw: object) -> OpsServer:
    base = dict(
        id=7,
        label="DE-1",
        host="node.example.com",
        port=2222,
        username="ubuntu",
        ip="203.0.113.7",
        country="DE",
        os="Ubuntu 24.04 <LTS>",
        host_key=HOSTKEY,
        key_ok=True,
        sudo_password="gv1:sealed",
        created_at=NOW,
        last_login_at=NOW,
    )
    base.update(kw)
    return OpsServer(**base)


def _draft(**kw: object) -> NodeDraft:
    base = dict(
        server_id=7,
        login="root@203.0.113.7",
        address="203.0.113.7",
        country="DE",
        name="🇩🇪 آلمان",
        name_auto=True,
        profiles=[
            ProfileChoice("p1", "Main <&>", 3, [(443, "tcp"), (8443, "udp")], 4),
            ProfileChoice("p2", "Spare", 1, [(80, "tcp")], 0),
        ],
        profile_uuid="p1",
        profile_why="4 نود دیگر هم همین را اجرا می‌کنند",
        node_port=2222,
        ssh_port=22,
        existing="کانتینر remnanode (Up 3 days, remnawave/node:latest)",
        warnings=["رم سرور کمه (400MB)"],
        facts={"os": "Ubuntu <24>", "arch": "x86_64", "mem_mb": 400, "disk_mb": 9000,
               "docker": "", "ufw": True, "isp": "Hetzner & Co"},
        node_names=["🇩🇪 آلمان 2"],
        key_ok=False,
        sudo_kept=True,
    )  # fmt: skip
    base.update(kw)
    return NodeDraft(**base)  # type: ignore[arg-type]


def _steps(failed: bool = True) -> list[dict]:
    return [
        {"key": "panel", "title": "دسترسی به پنل", "status": OK, "note": "3 نود", "detail": ""},
        {"key": "login", "title": "ورود <b>", "status": RUNNING, "note": "", "secs": 12},
        {
            "key": "check",
            "title": "بررسی سرور",
            "status": FAIL if failed else OK,
            "note": "«docker» خطا داد <&>",
            "detail": "E: Unable to locate <package>\n" * 3,
        },
    ]


def _job(kind: str, status: str = OpsJobStatus.ok, **kw: object) -> OpsJob:
    base = dict(
        id="0123456789abcdef",
        kind=kind,
        status=status,
        chat_id=1,
        message_id=10,
        lang="fa",
        params={"server_id": 7},
        result={"steps": _steps(status != OpsJobStatus.ok), "log": ["$ id -u", "  -> rc=0"]},
        error="به 1.2.3.4:22 وصل نشد <timeout>" if status != OpsJobStatus.ok else None,
        created_by=1,
        created_at=NOW,
        started_at=NOW,
        finished_at=NOW,
    )
    base.update(kw)
    return OpsJob(**base)


def _nodes() -> list[NodeInfo]:
    return [
        NodeInfo("u1", "🇩🇪 آلمان", "203.0.113.7", 2222, is_connected=True, country="DE",
                 users_online=12),
        NodeInfo("u2", "NL <1>", "198.51.100.2", 2222, last_status="connect ECONNREFUSED <x>",
                 country="NL"),
        NodeInfo("u3", "Old", "192.0.2.9", 2222, is_disabled=True),
    ]  # fmt: skip


def _screens():
    server = _server()
    draft = _draft()
    yield ops_view.queued_screen("🖥 نصب نود")
    yield ops_view.draft_screen("0123456789abcdef", draft, notice="✏️ &lt;done&gt; <b>ok</b>")
    yield ops_view.draft_screen("0123456789abcdef", _draft(blockers=["⛔ <blocked>"]))
    yield ops_view.profiles_screen("0123456789abcdef", draft)
    yield ops_view.name_prompt("0123456789abcdef", draft, problem="اسم <bad>")
    yield ops_view.country_prompt("0123456789abcdef", draft, problem="?")
    yield ops_view.nodes_screen(_nodes(), {"203.0.113.7": server})
    yield ops_view.nodes_screen([], {})
    yield ops_view.nodes_screen(None, {}, error="پنل: <html> 502")
    yield ops_view.servers_screen(
        [server, _server(id=8, label="X <y>", country="XX", key_ok=False)]
    )
    yield ops_view.servers_screen([])
    yield ops_view.server_screen(server)
    yield ops_view.server_screen(
        _server(sudo_password=None, host_key=None, os=""),
        test={"mem_mb": 2048, "disk_mb": 512, "docker": "27.3 <x>", "remnanode": "Up", "keys": 3},
    )
    yield ops_view.forget_confirm(server)
    yield ops_view.trust_confirm(server)
    yield ops_view.token_screen(
        {
            "missing": ["keygen:read"],
            "node": ["nodes:read", "keygen:read"],
            "features": [["🏷 <later>", ["x:read"]]],
        }
    )
    yield ops_view.token_screen({"missing": [], "node": ["nodes:read"], "features": []})
    yield ops_view.address_prompt(for_node=True, servers=[server], problem="<bad>")
    yield ops_view.address_prompt(for_node=False)
    yield ops_view.password_prompt("ubuntu@node.example.com:2222", why="کلید <x>")
    yield ops_view.vault_missing()
    yield ops_view.busy_screen(_job(JobKind.node_install, OpsJobStatus.running))
    yield ops_view.unknown_job()
    plan = {"name": "🇩🇪 <آلمان>", "address": "203.0.113.7", "port": 2222, "country": "DE",
            "profile_name": "Main", "files_written": True, "node_uuid": "n1"}  # fmt: skip
    yield ops_view.job_screen(
        _job(JobKind.node_prepare, result={"draft": draft.dump(), "steps": []})
    )
    yield ops_view.job_screen(
        _job(
            JobKind.node_install,
            result={
                "plan": plan,
                "node": {"xray": "25.9 <x>", "version": "2.1"},
                "inbounds_up": [[443, True], [8443, False]],
                "steps": _steps(False),
            },
        )
    )
    for status in (OpsJobStatus.failed, OpsJobStatus.interrupted):
        yield ops_view.job_screen(
            _job(JobKind.node_install, status, params={"draft": draft.dump()},
                 result={"plan": plan, "steps": _steps(), "code": "hostkey", "log": ["x"]}),
            server=server,
        )  # fmt: skip
    for kind in (JobKind.server_add, JobKind.server_test):
        yield ops_view.job_screen(_job(kind), server=server)
        yield ops_view.job_screen(_job(kind, OpsJobStatus.failed, result={"code": "auth"}))
    yield ops_view.job_screen(
        _job(JobKind.node_undo, result={"left": ["/opt/remnanode <x>"], "steps": _steps(False)})
    )
    yield ops_view.job_screen(
        _job(JobKind.server_forget, result={"label": "DE-1", "removed": True})
    )
    yield ops_view.job_screen(_job(JobKind.server_forget, OpsJobStatus.failed))
    yield ops_view.job_screen(_job(JobKind.panel_check, result={"missing": [], "node": []}))
    yield ops_view.job_screen(_job(JobKind.node_prepare, OpsJobStatus.running))


@pytest.mark.parametrize("look", [PLAIN, Look()])
def test_every_ops_screen_is_valid_markup(look: Look) -> None:
    drawn = list(_screens())
    for doc, markup in drawn:
        kinds = set()
        for v in screens.variants(doc, markup, look):
            problems = check_rich(v.body) if v.rich else check_classic(v.body)
            assert problems == [], (v.rich, v.themed, problems, v.body[:300])
            assert check_keyboard(v.markup) == [], v.markup
            kinds.add(v.rich)
        assert kinds == ({True, False} if look.rich else {False})
    assert len(drawn) > 30


def test_progress_is_valid_markup_and_names_the_running_step() -> None:
    rep = Reporter()
    rep.header = "🖥 افزودن نود «<x>» به پنل"
    rep.steps = []
    rep._get("panel", "دسترسی به پنل").status = OK
    rep._get("login", "ورود").status = RUNNING
    doc = ops_view.progress_doc(rep, started=0.0)
    for v in screens.variants(doc, None, Look()):
        assert (check_rich(v.body) if v.rich else check_classic(v.body)) == []
    text = doc.classic()
    assert "&lt;x&gt;" in text and "⏳ ورود" in text and "در حال انجام" in text


def test_every_ops_button_fits_telegram_and_is_namespaced() -> None:
    for _doc, markup in _screens():
        for row in markup.inline_keyboard:
            for b in row:
                assert b.callback_data and len(b.callback_data.encode()) <= 64, b.callback_data
                assert b.callback_data.startswith(("ops:", "admin:")), b.callback_data


def test_a_draft_with_problems_offers_no_install_button() -> None:
    _doc, markup = ops_view.draft_screen("j", _draft(blockers=["x"]))
    data = [b.callback_data for row in markup.inline_keyboard for b in row]
    assert cb.OPS_DRAFT_GO + "j" not in data
    _doc, markup = ops_view.draft_screen("j", _draft())
    data = [b.callback_data for row in markup.inline_keyboard for b in row]
    assert cb.OPS_DRAFT_GO + "j" in data


def test_a_failed_install_offers_undo_only_when_it_changed_something() -> None:
    done = {"plan": {"files_written": True}, "steps": []}
    nothing = {"plan": {"files_written": False}, "steps": []}
    for result, expected in ((done, True), (nothing, False)):
        job = _job(JobKind.node_install, OpsJobStatus.failed, result=result)
        _doc, markup = ops_view.job_screen(job)
        data = [b.callback_data for row in markup.inline_keyboard for b in row]
        assert (cb.OPS_JOB_UNDO + job.id in data) is expected


def test_the_log_file_carries_steps_and_lines() -> None:
    text = ops_view.log_text(_job(JobKind.node_install, OpsJobStatus.failed))
    assert "node_install" in text and "[fail] بررسی سرور" in text and "$ id -u" in text
