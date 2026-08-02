"""A single bad update must never wedge the webhook queue.

Regression for a live outage: a user who had blocked the bot sent /start, the handler's reply raised
``TelegramForbiddenError``, that propagated out of ``dp.feed_update`` to the route, FastAPI answered
Telegram 500 — and Telegram, treating 500 as "not delivered", redelivered the SAME update forever.
The backlog grew (29 pending) and the bot stopped answering EVERY user.

Two independent guarantees are asserted here:
1. the route ACKs 200 no matter what the dispatcher raises (so Telegram never retries), and
2. the dispatcher's error handler absorbs the exception and classifies an unreachable chat as
   routine rather than a fault.
"""

from __future__ import annotations

import os
from collections.abc import Iterator
from typing import Any

import pytest
from aiogram.exceptions import TelegramForbiddenError, TelegramNotFound, TelegramRetryAfter
from aiogram.methods import SendMessage
from fastapi.testclient import TestClient

from gozar.bot.errors import on_error
from gozar.config.settings import get_settings
from gozar.services.telegram_errors import is_unreachable
from gozar.web.app import create_app

_SEND = SendMessage(chat_id=1, text="x")  # the method an aiogram error must carry

# A minimal well-formed update; the dispatcher is stubbed, so only the shape has to parse.
_UPDATE: dict[str, Any] = {
    "update_id": 1,
    "message": {
        "message_id": 1,
        "date": 1,
        "chat": {"id": 42, "type": "private"},
        "from": {"id": 42, "is_bot": False, "first_name": "T"},
        "text": "/start",
    },
}


class _Boom:
    """Dispatcher stub whose feed_update always raises — stands in for any failing handler."""

    def __init__(self, exc: Exception) -> None:
        self.exc = exc
        self.calls = 0

    async def feed_update(self, *_a: object, **_kw: object) -> None:
        self.calls += 1
        raise self.exc


class _Session:
    async def close(self) -> None:  # the app's lifespan closes the bot session on shutdown
        return None


class _Bot:
    """Bot stub — only the update-parsing context and the lifespan's session.close() touch it."""

    def __init__(self) -> None:
        self.session = _Session()


@pytest.fixture(autouse=True)
def _webhook_secrets() -> Iterator[None]:
    """Give the route real secrets — with the defaults empty, /tg/{secret} can't even match."""
    previous = {k: os.environ.get(k) for k in ("WEBHOOK_SECRET", "WEBHOOK_HEADER_SECRET")}
    os.environ["WEBHOOK_SECRET"] = "path-secret"
    os.environ["WEBHOOK_HEADER_SECRET"] = "header-secret"
    get_settings.cache_clear()
    yield
    for key, value in previous.items():
        if value is None:
            os.environ.pop(key, None)
        else:
            os.environ[key] = value
    get_settings.cache_clear()


def _post(client: TestClient, body: Any) -> Any:
    s = get_settings()
    return client.post(
        f"/tg/{s.webhook_secret.get_secret_value()}",
        json=body,
        headers={"X-Telegram-Bot-Api-Secret-Token": s.webhook_header_secret.get_secret_value()},
    )


@pytest.mark.parametrize(
    "exc",
    [
        TelegramForbiddenError(method=_SEND, message="Forbidden: bot was blocked by the user"),
        RuntimeError("some unrelated handler bug"),
    ],
    ids=["blocked-user", "handler-bug"],
)
def test_webhook_acks_200_even_when_the_dispatcher_raises(exc: Exception) -> None:
    app = create_app()
    dp = _Boom(exc)
    with TestClient(app) as client:
        app.state.bot = _Bot()
        app.state.dp = dp
        res = _post(client, _UPDATE)
    # 200 is what stops Telegram from redelivering this update forever.
    assert res.status_code == 200, res.text
    assert dp.calls == 1


def test_webhook_acks_200_on_an_unparsable_payload() -> None:
    """Even a body that never becomes an Update is ACKed — retrying it could never succeed."""
    app = create_app()
    dp = _Boom(RuntimeError("unreachable"))
    with TestClient(app) as client:
        app.state.bot = _Bot()
        app.state.dp = dp
        res = _post(client, {"update_id": "not-an-int", "garbage": True})
    assert res.status_code == 200
    assert dp.calls == 0  # it failed while parsing, before reaching the dispatcher


async def test_error_handler_absorbs_the_exception() -> None:
    class _Event:
        def __init__(self, exc: Exception) -> None:
            self.exception = exc

    blocked = TelegramForbiddenError(method=_SEND, message="Forbidden: bot was blocked by the user")
    # True == "handled", so aiogram does not re-raise it into the route.
    assert await on_error(_Event(blocked)) is True  # type: ignore[arg-type]
    assert await on_error(_Event(RuntimeError("bug"))) is True  # type: ignore[arg-type]


def test_unreachable_classification_matches_the_broadcast_allowlist() -> None:
    def forbidden(msg: str) -> TelegramForbiddenError:
        return TelegramForbiddenError(method=_SEND, message=msg)

    assert is_unreachable(forbidden("Forbidden: bot was blocked by the user"))
    assert is_unreachable(forbidden("Forbidden: user is deactivated"))
    assert is_unreachable(TelegramNotFound(method=_SEND, message="Not Found: chat not found"))
    # Transient / unrelated failures must NOT be classified as permanent.
    assert not is_unreachable(TelegramRetryAfter(method=_SEND, message="Slow down", retry_after=5))
    assert not is_unreachable(forbidden("Forbidden: bot is not a member"))
    assert not is_unreachable(RuntimeError("boom"))
