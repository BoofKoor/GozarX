"""Classification of Telegram delivery failures — shared by the bot and the arq worker.

The single question both callers need answered: is this chat **permanently** unreachable (the user
blocked the bot, deleted their account, or the chat is gone), or is it a transient failure worth
another attempt? Getting that wrong in either direction is expensive: treating a transient error as
permanent deletes real users (the v1 mass-deletion bug), and treating a permanent one as transient
retries forever.

aiogram does not model these as distinct exception classes, so we match a substring of ``message``
— the raw "Forbidden: "/"Bad Request: " prefix and minor wording shifts don't matter.

"Chat not found" arrives as a ``TelegramBadRequest``: aiogram picks the class by HTTP status, and
Telegram answers ``sendMessage`` to a chat that no longer exists with a 400 ("Bad Request: chat not
found"). Matching only ``TelegramNotFound`` (a 404), the rule never fired and every gone chat was a
"failed" send on every broadcast, forever. ``TelegramNotFound`` is still accepted in case a method
answers with a real 404. A user this marks is only flagged unreachable — never deleted — and the
flag clears the next time they message the bot, so a wrong match costs one skipped broadcast.
"""

from __future__ import annotations

from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError, TelegramNotFound

BLOCKED = "bot was blocked by the user"
DEACTIVATED = "user is deactivated"
CHAT_NOT_FOUND = "chat not found"


def is_unreachable(exc: Exception) -> bool:
    """True only for the three permanent 'this chat is gone forever' delivery failures."""
    msg = str(getattr(exc, "message", exc)).lower()
    if isinstance(exc, TelegramForbiddenError):
        return BLOCKED in msg or DEACTIVATED in msg
    if isinstance(exc, (TelegramNotFound, TelegramBadRequest)):
        return CHAT_NOT_FOUND in msg
    return False
