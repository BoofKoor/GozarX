"""Admin console flows — the safety-critical bits: the broadcast preview gate only enqueues on
confirm, destructive single-user actions confirm first, and the console keeps ONE live screen (a
typed answer is consumed and the screen edited; a broadcast's source message is never deleted).

Handlers are called directly with a recording ``FakeConsole`` and stub state/arq (StateFilter is
dispatcher-level), fakeredis-backed content, no DB.
"""

from __future__ import annotations

from types import SimpleNamespace

import fakeredis.aioredis

from gozar.bot.handlers.admin import home, look, users
from gozar.bot.handlers.admin.fanout import (
    FanoutFlow,
    fanout_cancel,
    fanout_confirm,
    fanout_receive,
    reset_all_confirm,
    start_broadcast,
)
from gozar.bot.handlers.admin.users import UserActionFlow, user_ban_prompt, user_lookup, user_unban
from gozar.db.models.enums import Language, UserStatus
from gozar.db.models.user import User
from gozar.services.admin import ReclaimRefused, UserCard
from gozar.services.content import ContentService
from gozar.services.settings_service import SettingKey
from gozar.ui.buttons import EMPTY_OVERRIDES
from gozar.ui.look import PLAIN, Look
from gozar.ui.rich import Doc


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


class FakeLooks:
    def __init__(self) -> None:
        self.switches: dict[str, bool] = {}

    async def snapshot(self) -> Look:
        return Look(
            premium=self.switches.get(SettingKey.LOOK_PREMIUM, True),
            rich=self.switches.get(SettingKey.LOOK_RICH, True),
        )

    async def set_switch(self, key: str, on: bool) -> None:
        self.switches[key] = on

    async def blocked_reason(self) -> str | None:
        return None

    async def checked(self) -> None:
        return None

    async def take_notice(self) -> None:
        return None


class FakeStore:
    def __init__(self) -> None:
        self.live: int | None = None

    async def put(self, chat_id: int, message_id: int) -> None:
        self.live = message_id


class FakeConsole:
    """Records what the handlers put on the screen."""

    def __init__(self) -> None:
        self.shown: list[dict] = []
        self.consumed: list[object] = []
        self.look = PLAIN
        self.looks = FakeLooks()
        self.store = FakeStore()
        self.chat_id = 5
        self.bot = SimpleNamespace()
        self.lang = Language.en

    async def show(self, content, markup=None, *, at=None, new=False):  # noqa: ANN001, ANN201
        self.shown.append({"content": content, "markup": markup, "at": at, "new": new})
        return SimpleNamespace(message_id=100 + len(self.shown))

    async def consume(self, message: object) -> None:
        self.consumed.append(message)

    async def send(self, content, markup=None):  # noqa: ANN001, ANN201
        return SimpleNamespace(message_id=900)

    @property
    def last(self) -> dict:
        return self.shown[-1]


def _callback(uid: int = 5) -> SimpleNamespace:
    async def answer(*a: object, **k: object) -> None:
        return None

    return SimpleNamespace(
        answer=answer, message=SimpleNamespace(message_id=42), from_user=SimpleNamespace(id=uid)
    )


def _user() -> User:
    return User(telegram_id=5, language=Language.en)


def _text(content: object) -> str:
    return content.classic() if isinstance(content, Doc) else str(content)


async def test_start_broadcast_enters_waiting_state_on_the_same_screen() -> None:
    content = await _content(admin_broadcast_prompt="send the message")
    state = FakeState()
    console = FakeConsole()
    cb = _callback()
    await start_broadcast(cb, _user(), content, state, console, buttons=EMPTY_OVERRIDES)
    assert state.state == FanoutFlow.waiting_message
    assert (await state.get_data())["action"] == "broadcast"
    assert console.last["at"] is cb.message  # edited in place, not a new message
    assert "send the message" in _text(console.last["content"])


async def test_the_broadcast_source_is_never_deleted_and_the_gate_is_a_new_screen() -> None:
    # The worker copies the admin's message to every user: deleting it would break the send.
    content = await _content(admin_send_preview="send to {count}?")
    state = FakeState({"action": "broadcast"}, FanoutFlow.waiting_message)
    console = FakeConsole()
    echoed: list[int] = []

    async def copy_to(chat_id: int) -> None:
        echoed.append(chat_id)

    message = SimpleNamespace(chat=SimpleNamespace(id=77), message_id=300, copy_to=copy_to)

    class Users:
        async def count(self) -> int:
            return 12

    await fanout_receive(message, _user(), content, state, Users(), console, EMPTY_OVERRIDES)
    assert console.consumed == []
    assert echoed == [77]  # the preview, exactly as users will see it
    assert console.last["new"] is True  # under the preview, so "the preview above" holds
    assert "send to 12?" in _text(console.last["content"])
    assert (await state.get_data())["message_id"] == 300
    assert state.state == FanoutFlow.confirming


async def test_confirm_enqueues_fanout_and_clears() -> None:
    content = await _content(admin_send_queued="queued")
    state = FakeState(data={"action": "broadcast", "src_chat": 100, "message_id": 200})
    arq = FakeArq()
    await fanout_confirm(
        _callback(uid=5), _user(), content, state, arq, FakeConsole(), buttons=EMPTY_OVERRIDES
    )
    assert arq.jobs == [("fanout", ("broadcast", 100, 200, 5))]
    assert state.cleared


async def test_cancel_enqueues_nothing() -> None:
    content = await _content(admin_send_cancelled="cancelled")
    state = FakeState(data={"action": "broadcast", "src_chat": 100, "message_id": 200})
    await fanout_cancel(_callback(), _user(), content, state, FakeConsole(), EMPTY_OVERRIDES)
    assert state.cleared  # no arq involved → nothing can be sent


async def test_confirm_without_arq_is_safe() -> None:
    content = await _content(admin_send_failed="failed")
    state = FakeState(data={"action": "broadcast", "src_chat": 100, "message_id": 200})
    console = FakeConsole()
    await fanout_confirm(_callback(), _user(), content, state, None, console, EMPTY_OVERRIDES)
    assert state.cleared
    assert "failed" in _text(console.last["content"])


async def test_ban_action_confirms_before_acting() -> None:
    content = await _content(admin_ban_confirm="are you sure?")
    state = FakeState(data={"target_id": 77}, state=UserActionFlow.viewing)
    console = FakeConsole()
    await user_ban_prompt(_callback(), _user(), content, state, console, buttons=EMPTY_OVERRIDES)
    assert state.state == UserActionFlow.confirming
    assert (await state.get_data())["pending"] == "ban"
    confirm = console.last["markup"].inline_keyboard[0][0]
    assert confirm.style == "danger"  # what it confirms takes something away


async def test_reset_all_confirm_enqueues_bulk_job() -> None:
    content = await _content(admin_reset_all_queued="queued")
    arq = FakeArq()
    await reset_all_confirm(
        _callback(uid=5), _user(), content, arq, FakeConsole(), buttons=EMPTY_OVERRIDES
    )
    assert arq.jobs == [("reset_all_active", (5,))]


async def test_unban_says_the_panel_did_not_answer_instead_of_done(monkeypatch) -> None:
    # A revoke still pending from the ban must land before the unban: when it can't, the card must
    # not claim "unbanned" over a user who is still banned.
    notes: list[object] = []

    async def show_card(*args: object, at: object = None, note_key: object = None) -> None:
        notes.append(note_key)

    class Admin:
        async def unban(self, target_id: int) -> None:
            raise ReclaimRefused("panel")

    monkeypatch.setattr(users, "show_card", show_card)
    state = FakeState({"target_id": 9}, UserActionFlow.viewing)
    await user_unban(
        _callback(), _user(), await _content(), state, Admin(), FakeConsole(), None, EMPTY_OVERRIDES
    )
    assert notes == ["admin_reclaim_panel_down"]


async def test_a_typed_id_is_consumed_and_the_card_replaces_the_prompt() -> None:
    content = await _content()
    state = FakeState(state=UserActionFlow.waiting_id)
    console = FakeConsole()
    target = User(telegram_id=77, language=Language.fa, status=UserStatus.active_config)

    class Admin:
        async def lookup(self, target_id: int) -> UserCard:
            assert target_id == 77
            return UserCard(user=target, configs=3)

    message = SimpleNamespace(text=" 77 ")
    await user_lookup(message, _user(), content, state, Admin(), console, EMPTY_OVERRIDES)
    assert console.consumed == [message]  # the typed id does not stay in the chat
    assert console.last["at"] is None and console.last["new"] is False  # the live screen, edited
    assert state.state == UserActionFlow.viewing
    assert (await state.get_data())["target_id"] == 77
    assert "77" in _text(console.last["content"])


async def test_an_unknown_id_shows_the_prompt_again_with_the_error() -> None:
    content = await _content(admin_user_not_found="no such user", admin_user_prompt="send an id")
    state = FakeState(state=UserActionFlow.waiting_id)
    console = FakeConsole()

    class Admin:
        async def lookup(self, target_id: int) -> None:
            return None

    await user_lookup(
        SimpleNamespace(text="abc"), _user(), content, state, Admin(), console, EMPTY_OVERRIDES
    )
    shown = _text(console.last["content"])
    assert "no such user" in shown and "send an id" in shown
    assert state.state == UserActionFlow.waiting_id  # still waiting: just type another


async def test_admin_command_opens_a_fresh_screen(monkeypatch) -> None:
    seen: dict = {}

    async def show_home(*args: object, at: object = None, new: bool = False) -> None:
        seen.update(at=at, new=new)

    monkeypatch.setattr(home, "show_home", show_home)
    console = FakeConsole()
    state = FakeState({"action": "broadcast"}, FanoutFlow.waiting_message)
    message = SimpleNamespace()
    await home.open_admin(message, _user(), None, state, None, console, None, EMPTY_OVERRIDES)
    assert state.cleared  # /admin always gets out of a half-done flow
    assert console.consumed == [message]
    assert seen == {"at": None, "new": True}


async def test_simple_turns_both_switches_off() -> None:
    console = FakeConsole()
    console.look = Look()
    await look.simple(SimpleNamespace(), _user(), FakeState(), console.looks, console)
    assert console.looks.switches == {SettingKey.LOOK_PREMIUM: False, SettingKey.LOOK_RICH: False}
    assert console.look == PLAIN  # its own answer must not depend on the look
    assert console.last["new"] is True
