"""Owner-only Telegram console (``/admin``) — aiogram FSM on the shared Redis storage.

The whole router is gated by ``IsOwner`` (a non-owner's update never matches and falls through, so
the console never leaks); the filter is the PARENT router's, so it covers every section below.
``ConsoleMiddleware`` then hands each handler a ``Console``: the chat's one live screen, drawn with
the 🎨 look (rich messages, premium emoji, coloured buttons — ``bot/screens``).

Sections, in dispatch order: ``home`` and ``look`` first, so ``/admin`` and ``/simple`` win over a
flow that is waiting for typed input; then the screens; the two flows that read typed messages
(``users``, ``fanout``) last.

Bulk work (broadcast/forward fan-out, reset-all-active) runs in the worker — handlers only enqueue.
"""

from __future__ import annotations

from aiogram import Router

from gozar.bot.filters import IsOwner
from gozar.bot.handlers.admin import fanout, home, locations, look, stats, users
from gozar.bot.handlers.admin.console import Console, ConsoleMiddleware
from gozar.bot.handlers.admin.fanout import FanoutFlow
from gozar.bot.handlers.admin.users import UserActionFlow

router = Router(name="admin")
router.message.filter(IsOwner())
router.callback_query.filter(IsOwner())
router.message.middleware(ConsoleMiddleware())
router.callback_query.middleware(ConsoleMiddleware())
for section in (home, look, stats, locations, users, fanout):
    router.include_router(section.router)

__all__ = ["Console", "FanoutFlow", "UserActionFlow", "router"]
