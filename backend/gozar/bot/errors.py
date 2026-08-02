"""Global dispatcher error handler — the bot's last line of defence for a single bad update.

Without this, an exception raised inside a handler propagates out of ``dp.feed_update`` to the
FastAPI webhook route, which answers Telegram with 500. Telegram treats a non-2xx as "not
delivered" and redelivers the SAME update indefinitely, so one deterministically-failing update
(most commonly a user who blocked the bot, whose queued /start can never be answered) wedges the
queue and the bot stops responding for everybody.

Handled here:
- a permanently-unreachable chat (blocked / deactivated / chat-not-found) is expected, not a fault:
  log one info line, no traceback — there is nothing to deliver and nothing to retry;
- anything else is a real bug: log it with the traceback so it is visible, but still absorb it so a
  single broken update never blocks the rest.
"""

from __future__ import annotations

import logging

from aiogram import Dispatcher
from aiogram.types import ErrorEvent

from gozar.services.telegram_errors import is_unreachable

logger = logging.getLogger(__name__)


async def on_error(event: ErrorEvent) -> bool:
    """Absorb the exception. Returning True marks the update handled so aiogram won't re-raise."""
    exc = event.exception
    if is_unreachable(exc):
        # Nothing to do: the user blocked the bot / deleted their account. Not an error condition,
        # and NOT a reason to touch their row here — removal belongs to the broadcast path, which
        # applies the same allowlist while it fans out.
        logger.info("update dropped — chat unreachable: %s", type(exc).__name__)
    else:
        logger.exception("unhandled error while processing update", exc_info=exc)
    return True


def register_error_handler(dp: Dispatcher) -> None:
    dp.errors.register(on_error)
