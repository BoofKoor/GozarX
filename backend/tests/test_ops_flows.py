"""🖥 nodes / 🗄 servers console flows — above all what happens to a password: the message is
consumed before anything else, the password reaches Redis only sealed for its one job, and it is
never in FSM data, a job's params or a screen. Plus one job per chat, a stale job closed on the
way, a saved server needing no password, the draft's edits, and forgetting a server.

Handlers are called directly (StateFilter is dispatcher-level) with a recording console, a real
database session, fakeredis and a recording arq.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import fakeredis.aioredis
import pytest

from gozar import vault
from gozar.bot import callbacks as cb
from gozar.bot.handlers.admin import nodes, servers
from gozar.bot.handlers.admin.nodes import OpsFlow
from gozar.db.models.enums import Language
from gozar.db.models.ops import OpsJob, OpsJobStatus, OpsServer
from gozar.db.models.user import User
from gozar.db.repositories.ops import OpsJobRepository, OpsServerRepository
from gozar.services.node_draft import NodeDraft, ProfileChoice
from gozar.services.ops import JOB_FUNCTION, SECRET_TTL, JobKind, take_over
from gozar.ui.buttons import EMPTY_OVERRIDES
from gozar.ui.rich import Doc
from tests.test_admin_flows import FakeConsole, FakeState

KEY = vault.parse_key(vault.new_key_text())
PASSWORD = "Sup3r-secret pass!"
B = EMPTY_OVERRIDES


@pytest.fixture(autouse=True)
def _vault(monkeypatch):
    monkeypatch.setattr(vault, "_key", lambda key=None: KEY)


class RecordingState(FakeState):
    """FSM state that remembers every value ever written to it — a password stored for a moment
    and cleared again still sat in Redis."""

    def __init__(self, *a: object, **k: object) -> None:
        super().__init__(*a, **k)
        self.written: list[object] = []

    async def update_data(self, **kw: object) -> None:
        self.written.append(kw)
        await super().update_data(**kw)

    async def set_data(self, data: dict) -> None:
        self.written.append(data)
        self._data = dict(data)


class Store:
    def __init__(self) -> None:
        self.live: int | None = 42

    async def put(self, chat_id: int, message_id: int) -> None:
        self.live = message_id

    async def get(self, chat_id: int) -> int | None:
        return self.live


class Arq:
    def __init__(self) -> None:
        self.jobs: list[tuple] = []

    async def enqueue_job(self, name: str, *args: object, **kw: object) -> None:
        self.jobs.append((name, args, kw))


def _console() -> FakeConsole:
    console = FakeConsole()
    console.store = Store()
    console.lang = Language.fa
    return console


def _user() -> User:
    return User(telegram_id=5, language=Language.fa)


def _callback(data: str) -> SimpleNamespace:
    async def answer(*a: object, **k: object) -> None:
        return None

    return SimpleNamespace(
        data=data, answer=answer, message=SimpleNamespace(message_id=42), from_user=None
    )


def _message(text: str) -> SimpleNamespace:
    return SimpleNamespace(text=text)


def _text(content: object) -> str:
    return content.classic() if isinstance(content, Doc) else str(content)


def _redis():
    return fakeredis.aioredis.FakeRedis(decode_responses=True)


async def _server(session, **kw: object) -> OpsServer:
    row = OpsServer(
        label=kw.pop("label", "DE-1"),
        host=kw.pop("host", "203.0.113.7"),
        port=kw.pop("port", 22),
        username=kw.pop("username", "root"),
        key_ok=kw.pop("key_ok", True),
        host_key=kw.pop("host_key", "ssh-ed25519 AAAA"),
        **kw,
    )
    return await OpsServerRepository(session).add(row)


def _draft(server_id: int) -> NodeDraft:
    return NodeDraft(
        server_id=server_id,
        login="root@203.0.113.7",
        address="203.0.113.7",
        country="DE",
        name="🇩🇪 آلمان",
        name_auto=True,
        profiles=[
            ProfileChoice("p1", "Main", 1, [(443, "tcp")], 2),
            ProfileChoice("p2", "Alt", 1, [(8443, "tcp")], 0),
        ],
        profile_uuid="p1",
        profile_why="",
        node_port=2222,
        ssh_port=22,
        existing="",
        listeners=[("tcp", 8443, "nginx", [9])],
        node_names=["🇳🇱 هلند"],
    )


async def _prepared(session, server: OpsServer) -> OpsJob:
    job = await OpsJobRepository(session).create(
        kind=JobKind.node_prepare, chat_id=5, message_id=42, lang="fa",
        params={"server_id": server.id}, created_by=5,
    )  # fmt: skip
    await OpsJobRepository(session).finish(job, ok=True, result={"draft": _draft(server.id).dump()})
    return job


async def _jobs(session) -> list[OpsJob]:
    from sqlalchemy import select

    return list((await session.scalars(select(OpsJob).order_by(OpsJob.created_at))).all())


# ---- the password ------------------------------------------------------------------------------
async def test_a_typed_password_is_consumed_first_and_reaches_redis_only_sealed(session) -> None:
    console, state, arq, redis = _console(), RecordingState(), Arq(), _redis()
    await state.set_state(OpsFlow.password)
    await state.update_data(
        purpose=JobKind.node_prepare, target={"host": "203.0.113.9", "port": 22, "username": "root"}
    )
    msg = _message(PASSWORD)
    await nodes.password_typed(msg, state, console, session, redis, arq, _user(), B)

    assert console.consumed == [msg]  # out of the chat
    assert state.cleared and state.state is None
    (job,) = await _jobs(session)
    assert job.kind == JobKind.node_prepare and job.status == OpsJobStatus.queued
    assert job.params == {"host": "203.0.113.9", "port": 22, "username": "root"}
    assert arq.jobs == [(JOB_FUNCTION, (job.id,), {"_job_id": f"ops:{job.id}"})]
    raw = await redis.get(f"ops:secret:{job.id}")
    assert raw and PASSWORD not in raw and 0 < await redis.ttl(f"ops:secret:{job.id}") <= SECRET_TTL
    assert await take_over(redis, job.id) == PASSWORD
    everything = repr(state.written) + repr(job.params) + repr(job.result)
    everything += "".join(_text(s["content"]) for s in console.shown)
    assert PASSWORD not in everything
    assert console.last["at"] is None  # the live screen becomes the job's progress message


async def test_an_empty_or_orphan_password_message_starts_nothing(session) -> None:
    console, state, arq = _console(), FakeState(), Arq()
    await state.set_state(OpsFlow.password)  # no purpose: a state left from an old flow
    msg = _message(PASSWORD)
    await nodes.password_typed(msg, state, console, session, _redis(), arq, _user(), B)
    assert console.consumed == [msg] and arq.jobs == [] and await _jobs(session) == []


# ---- addresses ---------------------------------------------------------------------------------
async def test_an_unreadable_address_asks_again(session) -> None:
    console, state = _console(), FakeState({"for_node": True}, OpsFlow.address)
    msg = _message("not an address")
    await nodes.address_typed(msg, state, console, session, _redis(), Arq(), _user(), B)
    assert console.consumed == [msg] and state.state == OpsFlow.address
    assert "خوانده نشد" in _text(console.last["content"])


async def test_a_new_server_asks_its_password_and_a_saved_one_does_not(session) -> None:
    console, state, arq = _console(), FakeState({"for_node": True}, OpsFlow.address), Arq()
    await nodes.address_typed(
        _message("ubuntu@198.51.100.4:2200"), state, console, session, _redis(), arq, _user(), B
    )
    assert state.state == OpsFlow.password and arq.jobs == []
    data = await state.get_data()
    assert data["purpose"] == JobKind.node_prepare
    assert data["target"] == {"host": "198.51.100.4", "port": 2200, "username": "ubuntu"}
    assert "ubuntu@198.51.100.4:2200" in _text(console.last["content"])

    server = await _server(session)
    console, state, arq, redis = (
        _console(),
        FakeState({"for_node": True}, OpsFlow.address),
        Arq(),
        _redis(),
    )
    await nodes.address_typed(
        _message("203.0.113.7"), state, console, session, redis, arq, _user(), B
    )
    (job,) = await _jobs(session)
    assert job.params == {"server_id": server.id} and len(arq.jobs) == 1
    assert await redis.keys("ops:secret:*") == []  # the bot's key, no password


# ---- one job at a time -------------------------------------------------------------------------
async def test_a_second_job_waits_for_the_first_and_a_stale_one_is_closed(session) -> None:
    server = await _server(session)
    repo = OpsJobRepository(session)
    running = await repo.create(
        kind=JobKind.server_test, chat_id=5, message_id=1, lang="fa", params={}, created_by=5
    )
    await repo.start(running)
    console, arq = _console(), Arq()
    await servers.server_test(
        _callback(cb.OPS_SERVER_TEST + str(server.id)), console, session, _redis(), arq, _user(), B
    )
    assert arq.jobs == [] and "در جریان است" in _text(console.last["content"])

    running.started_at = datetime.now(UTC) - timedelta(hours=2)  # its worker died long ago
    await session.flush()
    await servers.server_test(
        _callback(cb.OPS_SERVER_TEST + str(server.id)), console, session, _redis(), arq, _user(), B
    )
    assert len(arq.jobs) == 1
    await session.refresh(running)
    assert running.status == OpsJobStatus.failed and running.error

    queued = (await _jobs(session))[-1]
    queued.created_at = datetime.now(UTC) - timedelta(seconds=SECRET_TTL + 5)  # never picked up
    await session.flush()
    await servers.server_test(
        _callback(cb.OPS_SERVER_TEST + str(server.id)), console, session, _redis(), arq, _user(), B
    )
    assert len(arq.jobs) == 2
    await session.refresh(queued)
    assert queued.status == OpsJobStatus.failed


async def test_without_vault_key_no_ssh_flow_starts(session, monkeypatch) -> None:
    def missing(key=None):  # noqa: ANN001, ANN202
        raise vault.VaultError("VAULT_KEY is not set")

    monkeypatch.setattr(vault, "_key", missing)
    console, state = _console(), FakeState()
    await nodes.node_add(_callback(cb.OPS_NODES_ADD), state, console, session, B)
    assert state.state is None and "VAULT_KEY" in _text(console.last["content"])


# ---- the draft ---------------------------------------------------------------------------------
async def test_install_goes_straight_on_with_the_key_and_asks_a_password_without_it(
    session,
) -> None:
    server = await _server(session)
    job = await _prepared(session, server)
    console, state, arq = _console(), FakeState(), Arq()
    await nodes.draft_go(
        _callback(cb.OPS_DRAFT_GO + job.id), state, console, session, _redis(), arq, _user(), B
    )
    install = (await _jobs(session))[-1]
    assert install.kind == JobKind.node_install and len(arq.jobs) == 1
    assert install.params["draft"]["server_id"] == server.id

    install.status = OpsJobStatus.ok  # free the chat
    server.key_ok = False
    await session.flush()
    console, state, arq = _console(), FakeState(), Arq()
    await nodes.draft_go(
        _callback(cb.OPS_DRAFT_GO + job.id), state, console, session, _redis(), arq, _user(), B
    )
    assert arq.jobs == [] and state.state == OpsFlow.password
    assert (await state.get_data())["purpose"] == JobKind.node_install


async def test_the_drafts_edits_live_in_fsm_data_and_redraw_the_summary(session) -> None:
    server = await _server(session)
    job = await _prepared(session, server)
    console, state = _console(), FakeState()
    await nodes.draft_name(_callback(cb.OPS_DRAFT_NAME + job.id), state, console, session, B)
    assert state.state == OpsFlow.name
    await nodes.name_typed(_message("🇳🇱 هلند"), state, console, B)  # taken in the panel
    assert state.state == OpsFlow.name and "⚠️" in _text(console.last["content"])
    await nodes.name_typed(_message("Frankfurt-1"), state, console, B)
    assert state.state is None
    assert NodeDraft.load((await state.get_data())["draft"]).name == "Frankfurt-1"
    assert "Frankfurt-1" in _text(console.last["content"])

    await nodes.draft_pick(_callback(f"{cb.OPS_DRAFT_PICK}{job.id}:1"), state, console, session, B)
    draft = NodeDraft.load((await state.get_data())["draft"])
    assert draft.profile_uuid == "p2" and draft.conflicts  # 8443 is nginx's
    assert cb.OPS_DRAFT_GO + job.id not in repr(console.last["markup"])

    await nodes.draft_country(_callback(cb.OPS_DRAFT_COUNTRY + job.id), state, console, session, B)
    await nodes.country_typed(_message("فنلاند"), state, console, B)
    assert NodeDraft.load((await state.get_data())["draft"]).country == "FI"


async def test_a_summary_from_an_old_prepare_still_opens(session) -> None:
    server = await _server(session)
    job = await _prepared(session, server)
    console, state = _console(), FakeState({"draft_job": "another", "draft": {}})
    await nodes.draft_back(_callback(cb.OPS_DRAFT_BACK + job.id), state, console, session, B)
    assert (await state.get_data())["draft_job"] == job.id
    assert "نود جدید" in _text(console.last["content"])


# ---- after a job -------------------------------------------------------------------------------
async def test_undo_and_retry_queue_the_right_job(session) -> None:
    server = await _server(session)
    repo = OpsJobRepository(session)
    install = await repo.create(
        kind=JobKind.node_install, chat_id=5, message_id=1, lang="fa",
        params={"draft": _draft(server.id).dump()}, created_by=5,
    )  # fmt: skip
    await repo.finish(install, ok=False, result={"plan": {"files_written": True}}, error="x")
    console, arq = _console(), Arq()
    await nodes.job_undo(
        _callback(cb.OPS_JOB_UNDO + install.id), console, session, _redis(), arq, _user(), B
    )
    undo = (await _jobs(session))[-1]
    assert undo.kind == JobKind.node_undo and undo.params == {"install_job": install.id}
    undo.status = OpsJobStatus.ok
    await session.flush()
    await nodes.job_retry(
        _callback(cb.OPS_JOB_RETRY + install.id), FakeState(), console, session, _redis(), arq,
        _user(), B,
    )  # fmt: skip
    again = (await _jobs(session))[-1]
    assert again.kind == JobKind.node_prepare and again.params == {"server_id": server.id}


# ---- 🗄 servers -----------------------------------------------------------------------------------
async def test_forgetting_a_server_the_key_no_longer_opens_drops_only_the_row(session) -> None:
    gone = await _server(session, key_ok=False)
    console, arq = _console(), Arq()
    await servers.server_forget_ok(
        _callback(cb.OPS_SERVER_FORGET_OK + str(gone.id)), console, session, _redis(), arq,
        _user(), B,
    )  # fmt: skip
    assert arq.jobs == [] and await OpsServerRepository(session).get(gone.id) is None
    assert "دستی" in _text(console.last["content"])
    live = await _server(session, label="NL-1", host="198.51.100.1")
    await servers.server_forget_ok(
        _callback(cb.OPS_SERVER_FORGET_OK + str(live.id)), console, session, _redis(), arq,
        _user(), B,
    )  # fmt: skip
    assert len(arq.jobs) == 1 and (await _jobs(session))[-1].kind == JobKind.server_forget


async def test_a_new_host_key_is_accepted_only_after_asking(session) -> None:
    server = await _server(session)
    console = _console()
    await servers.server_trust(_callback(cb.OPS_SERVER_TRUST + str(server.id)), console, session, B)
    assert server.host_key and "♻️ قبول" in repr(console.last["markup"])
    await servers.server_trust(
        _callback(cb.OPS_SERVER_TRUST + f"{server.id}:ok"), console, session, B
    )
    assert server.host_key is None
