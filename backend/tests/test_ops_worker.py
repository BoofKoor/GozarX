"""The worker's side of an SSH job (``worker/ops``): the row's life (queued → running → ok / failed
/ interrupted), the password handed to the body once and gone from Redis, a failure recorded with
what the console needs next (code, steps, plan, log), an install's plan on the row while it runs,
and a job a dead worker left running closed at the next start — its message saying so."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime

import fakeredis.aioredis
import pytest
from aiogram.exceptions import TelegramBadRequest
from aiogram.methods import SendMessage
from aiogram.types import Chat, Message

from gozar import vault
from gozar.db.models.ops import OpsJob, OpsJobStatus
from gozar.db.repositories.ops import OpsJobRepository
from gozar.ops.errors import RemoteError
from gozar.ops.node import NodePlan
from gozar.services.ops import JobKind, hand_over
from gozar.worker import ops as worker_ops

KEY = vault.parse_key(vault.new_key_text())


@pytest.fixture(autouse=True)
def _vault(monkeypatch):
    monkeypatch.setattr(vault, "_key", lambda key=None: KEY)


class Bot:
    """Telegram, for the reporter: regular messages only; remembers what was drawn."""

    def __init__(self) -> None:
        self.drawn: list[str] = []

    def _msg(self, message_id: int, text: str) -> Message:
        self.drawn.append(text)
        return Message(
            message_id=message_id,
            date=datetime.now(UTC),
            chat=Chat(id=1, type="private"),
            text=text,
        )

    async def send_rich_message(self, *a: object, **k: object) -> Message:
        raise TelegramBadRequest(SendMessage(chat_id=1, text="x"), "no rich here")

    async def send_message(self, chat_id: int, text: str, **k: object) -> Message:
        return self._msg(900, text)

    async def edit_message_text(self, text: str | None = None, **k: object) -> Message:
        if k.get("rich_message") is not None:
            raise TelegramBadRequest(SendMessage(chat_id=1, text="x"), "no rich here")
        return self._msg(int(k.get("message_id") or 1), text or "")

    async def delete_message(self, *a: object) -> bool:
        return True


class Panel:
    def ops(self) -> object:
        return object()


async def _job(sm, kind: str = JobKind.server_test, status: str = OpsJobStatus.queued) -> str:
    async with sm() as s:
        job = await OpsJobRepository(s).create(
            kind=kind, chat_id=1, message_id=10, lang="fa", params={"server_id": 1}, created_by=1
        )
        job.status = status
        await s.commit()
        return job.id


async def _row(sm, job_id: str) -> OpsJob:
    async with sm() as s:
        return await s.get(OpsJob, job_id)


def _ctx(sm, redis, bot) -> dict:
    return {"sessionmaker": sm, "cache_redis": redis, "bot": bot, "http": None, "panel": Panel()}


async def test_a_job_gets_its_password_once_and_closes_ok(db_sessions, monkeypatch) -> None:
    redis = fakeredis.aioredis.FakeRedis(decode_responses=True)
    seen = {}

    async def body(env):  # noqa: ANN001, ANN202
        seen["secret"] = env.secret
        await env.rep.plan([("login", "ورود")], header="🔌 تست")
        async with env.rep.stage("login") as st:
            await st.note("وصل شدم")
        return {"server_id": 1, "fine": True}

    monkeypatch.setitem(worker_ops.BODIES, JobKind.server_test, body)
    job_id = await _job(db_sessions)
    await hand_over(redis, job_id, "pw-123")
    bot = Bot()
    await worker_ops.ops_run(_ctx(db_sessions, redis, bot), job_id)

    row = await _row(db_sessions, job_id)
    assert seen["secret"] == "pw-123" and await redis.keys("ops:secret:*") == []
    assert row.status == OpsJobStatus.ok and row.result["fine"] is True
    assert row.result["steps"][0]["status"] == "ok" and "log" not in row.result
    assert row.started_at and row.finished_at and row.error is None
    assert "pw-123" not in repr(row.result) + "".join(bot.drawn)

    await worker_ops.ops_run(_ctx(db_sessions, redis, bot), job_id)  # a duplicate delivery
    assert (await _row(db_sessions, job_id)).finished_at == row.finished_at


async def test_a_failure_keeps_its_code_steps_plan_and_log(db_sessions, monkeypatch) -> None:
    redis = fakeredis.aioredis.FakeRedis(decode_responses=True)
    mid_run = {}

    async def body(env):  # noqa: ANN001, ANN202
        await env.rep.plan([("check", "بررسی"), ("panel", "ثبت")], header="🖥 نصب")
        plan = NodePlan("panel", "🇩🇪 آلمان", "203.0.113.7", "DE", "p1", files_written=True)
        env.rep.context["node_plan"] = plan
        async with env.rep.stage("check"):
            pass
        async with sm() as s:  # the plan is on the row while the job still runs
            mid_run["plan"] = (await s.get(OpsJob, env.job.id)).result
        env.rep.debug("$ docker compose up -d")
        async with env.rep.stage("panel"):
            raise RemoteError("پنل: نودی با همین اسم توی پنل هست", "A033", code="name_taken")

    sm = db_sessions
    monkeypatch.setitem(worker_ops.BODIES, JobKind.node_install, body)
    job_id = await _job(sm, JobKind.node_install)
    bot = Bot()
    await worker_ops.ops_run(_ctx(sm, redis, bot), job_id)

    row = await _row(sm, job_id)
    assert row.status == OpsJobStatus.failed and "همین اسم" in row.error
    assert row.result["code"] == "name_taken" and row.result["step"] == "panel"
    assert row.result["plan"]["files_written"] is True
    assert mid_run["plan"]["plan"]["name"] == "🇩🇪 آلمان"
    assert any("docker compose" in line for line in row.result["log"])
    assert "🧹" in bot.drawn[-1]  # the last screen offers undo: the install changed things


async def test_a_job_cancelled_mid_way_is_interrupted(db_sessions, monkeypatch) -> None:
    redis = fakeredis.aioredis.FakeRedis(decode_responses=True)

    async def body(env):  # noqa: ANN001, ANN202
        raise asyncio.CancelledError

    monkeypatch.setitem(worker_ops.BODIES, JobKind.server_test, body)
    job_id = await _job(db_sessions)
    with pytest.raises(asyncio.CancelledError):
        await worker_ops.ops_run(_ctx(db_sessions, redis, Bot()), job_id)
    row = await _row(db_sessions, job_id)
    assert row.status == OpsJobStatus.interrupted and row.finished_at


async def test_an_unexpected_error_is_an_internal_failure_not_a_crash(db_sessions, monkeypatch):
    redis = fakeredis.aioredis.FakeRedis(decode_responses=True)

    async def body(env):  # noqa: ANN001, ANN202
        raise ValueError("boom")

    monkeypatch.setitem(worker_ops.BODIES, JobKind.server_test, body)
    job_id = await _job(db_sessions)
    await worker_ops.ops_run(_ctx(db_sessions, redis, Bot()), job_id)
    row = await _row(db_sessions, job_id)
    assert row.status == OpsJobStatus.failed and "خطای داخلی" in row.error


async def test_a_job_left_running_is_closed_at_start_and_its_message_says_so(db_sessions):
    redis = fakeredis.aioredis.FakeRedis(decode_responses=True)
    job_id = await _job(db_sessions, status=OpsJobStatus.running)
    queued = await _job(db_sessions)
    bot = Bot()
    await worker_ops.close_interrupted(_ctx(db_sessions, redis, bot))
    assert (await _row(db_sessions, job_id)).status == OpsJobStatus.interrupted
    assert (await _row(db_sessions, queued)).status == OpsJobStatus.queued  # still to run
    assert len(bot.drawn) == 1 and "نیمه‌کاره" in bot.drawn[0]
