"""Admin FSM flows — the safety-critical bits: the broadcast preview gate only enqueues on confirm,
and destructive single-user actions confirm first. Handlers are called directly with stub
callback/state/arq (StateFilter is dispatcher-level), fakeredis-backed content, no DB.
"""

from __future__ import annotations

from types import SimpleNamespace

import fakeredis.aioredis

from gozar.bot.handlers.admin import (
    FanoutFlow,
    UserActionFlow,
    fanout_cancel,
    fanout_confirm,
    reset_all_confirm,
    start_broadcast,
    user_ban_prompt,
)
from gozar.db.models.enums import Language
from gozar.db.models.user import User
from gozar.services.content import ContentService


async def _content(**entries: str) -> ContentService:
    redis = fakeredis.aioredis.FakeRedis(decode_responses=True)
    for key, body in entries.items():
        await redis.set(f"cache:content:en:{key}", body)
    return ContentService(None, redis)  # type: ignore[arg-type]


class FakeState:
    def __init__(self, data: dict | None = None, state: object = None) -> None:
        self._data = dict(data or {})
        self.state = state
        self.cleared = False

    async def get_data(self) -> dict:
        return dict(self._data)

    async def update_data(self, **kw: object) -> None:
        self._data.update(kw)

    async def set_state(self, state: object) -> None:
        self.state = state

    async def clear(self) -> None:
        self._data = {}
        self.state = None
        self.cleared = True


class FakeArq:
    def __init__(self) -> None:
        self.jobs: list[tuple] = []

    async def enqueue_job(self, name: str, *args: object) -> None:
        self.jobs.append((name, args))


def _callback(uid: int = 5) -> SimpleNamespace:
    async def answer(*a: object, **k: object) -> None:
        return None

    return SimpleNamespace(
        answer=answer, message=None, from_user=SimpleNamespace(id=uid), data=None
    )


def _user() -> User:
    return User(telegram_id=5, language=Language.en)


async def test_start_broadcast_enters_waiting_state() -> None:
    content = await _content(admin_broadcast_prompt="send the message")
    state = FakeState()
    await start_broadcast(_callback(), _user(), content, state)
    assert state.state == FanoutFlow.waiting_message
    assert (await state.get_data())["action"] == "broadcast"


async def test_confirm_enqueues_fanout_and_clears() -> None:
    content = await _content(admin_send_queued="queued")
    state = FakeState(data={"action": "broadcast", "src_chat": 100, "message_id": 200})
    arq = FakeArq()
    await fanout_confirm(_callback(uid=5), _user(), content, state, arq)
    assert arq.jobs == [("fanout", ("broadcast", 100, 200, 5))]
    assert state.cleared


async def test_cancel_enqueues_nothing() -> None:
    content = await _content(admin_send_cancelled="cancelled")
    state = FakeState(data={"action": "broadcast", "src_chat": 100, "message_id": 200})
    await fanout_cancel(_callback(), _user(), content, state)
    assert state.cleared  # no arq involved → nothing can be sent


async def test_confirm_without_arq_is_safe() -> None:
    content = await _content(admin_send_failed="failed")
    state = FakeState(data={"action": "broadcast", "src_chat": 100, "message_id": 200})
    await fanout_confirm(_callback(), _user(), content, state, None)  # must not raise
    assert state.cleared


async def test_ban_action_confirms_before_acting() -> None:
    content = await _content(admin_ban_confirm="are you sure?")
    state = FakeState(data={"target_id": 77}, state=UserActionFlow.viewing)
    await user_ban_prompt(_callback(), _user(), content, state)
    assert state.state == UserActionFlow.confirming
    assert (await state.get_data())["pending"] == "ban"


async def test_reset_all_confirm_enqueues_bulk_job() -> None:
    content = await _content(admin_reset_all_queued="queued")
    arq = FakeArq()
    await reset_all_confirm(_callback(uid=5), _user(), content, arq)
    assert arq.jobs == [("reset_all_active", (5,))]
