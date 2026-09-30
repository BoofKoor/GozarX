"""An interrupted broadcast still says how far it got (DB-gated).

Every deploy restarts the worker, and arq CANCELS a running job on SIGTERM. CancelledError is not an
Exception, so the fan-out's bookkeeping used to be skipped entirely: the row sat on "sending" with
0/0/0 forever and the history polled it every five seconds.
"""

from __future__ import annotations

import asyncio
from types import SimpleNamespace

import pytest

from gozar.db.models.broadcast_log import BroadcastStatus
from gozar.db.models.user import User
from gozar.db.repositories.broadcast_log import BroadcastLogRepository
from gozar.worker.main import _close_interrupted_sends
from gozar.worker.tasks import broadcast_text


class _CancellingBot:
    """Delivers the first ``ok`` messages, then the worker is 'stopped' mid-send."""

    def __init__(self, ok: int) -> None:
        self.ok = ok
        self.sent = 0

    async def send_message(self, chat_id: int, text: str, **kw: object) -> SimpleNamespace:
        if chat_id < 0:  # the operator's progress message
            return SimpleNamespace(chat=SimpleNamespace(id=chat_id), message_id=1)
        if self.sent >= self.ok:
            raise asyncio.CancelledError
        self.sent += 1
        return SimpleNamespace(chat=SimpleNamespace(id=chat_id), message_id=1)

    async def edit_message_text(self, *args: object, **kw: object) -> None:
        return None


async def _seed(db_sessions, n: int) -> int:
    async with db_sessions() as session:
        session.add_all([User(telegram_id=1000 + i) for i in range(n)])
        log = await BroadcastLogRepository(session).create(
            body="hi",
            languages="",
            only_active=False,
            only_referrers=False,
            buttons=None,
            recipients=999,  # a stale enqueue-time count: the worker replaces it with the real one
        )
        await session.commit()
        return log.id


async def test_a_cancelled_broadcast_records_its_partial_counts(db_sessions, monkeypatch) -> None:
    async def _no_sleep(*_: object) -> None:
        return None

    monkeypatch.setattr("gozar.worker.tasks.asyncio.sleep", _no_sleep)
    log_id = await _seed(db_sessions, 45)
    ctx = {"bot": _CancellingBot(ok=20), "sessionmaker": db_sessions}
    with pytest.raises(asyncio.CancelledError):
        await broadcast_text(ctx, "hi", admin_id=-1, log_id=log_id)
    async with db_sessions() as session:
        row = await BroadcastLogRepository(session).get(log_id)
    assert row.status == BroadcastStatus.failed and row.finished_at is not None
    assert row.sent == 20  # the first chunk went out before the stop
    assert row.recipients == 45  # the audience actually walked, not the stale enqueue count


async def test_worker_start_closes_rows_left_sending(db_sessions) -> None:
    log_id = await _seed(db_sessions, 0)
    async with db_sessions() as session:
        repo = BroadcastLogRepository(session)
        await repo.mark_sending(log_id)
        await repo.record_progress(log_id, sent=7, failed=1, removed=0)
        await session.commit()
    await _close_interrupted_sends({"sessionmaker": db_sessions})
    async with db_sessions() as session:
        row = await BroadcastLogRepository(session).get(log_id)
    assert row.status == BroadcastStatus.failed and (row.sent, row.failed) == (7, 1)
