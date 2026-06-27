"""arq worker tasks — bulk fan-out that must never run inside a bot handler.

``fanout`` delivers one message to every user (broadcast = ``copy_message``, no "Forwarded from";
forward = ``forward_message``, keeps the header). It removes a user **only** on a genuine permanent
delivery failure (blocked / deactivated / chat-not-found) — never on a transient error (v1 lesson
#4). ``reset_all_active`` zeroes panel traffic consumption for every active user. Both report
progress to the admin's chat and make a single bounded panel/send attempt per user.
"""

from __future__ import annotations

import asyncio
import logging

from aiogram import Bot
from aiogram.exceptions import (
    TelegramAPIError,
    TelegramBadRequest,
    TelegramForbiddenError,
    TelegramRetryAfter,
)
from aiogram.types import Message

from gozar.db.models.enums import UserStatus
from gozar.db.repositories.user import UserRepository
from gozar.remnawave import RemnawaveError

logger = logging.getLogger("gozar.worker.tasks")

# The ONLY delivery failures that remove a user. Anything else (rate limit, network, 5xx, any other
# Forbidden/BadRequest description) is transient → keep the user. VERIFY the exact aiogram messages
# against the live API before trusting this allowlist.
_BLOCKED = "bot was blocked by the user"
_DEACTIVATED = "user is deactivated"
_CHAT_NOT_FOUND = "chat not found"

# Fan-out throttle: ~25 sends/s, comfortably under Telegram's ~30/s broadcast ceiling.
_SEND_DELAY = 0.04


def _should_remove(exc: Exception) -> bool:
    """True only for the three permanent 'this user is unreachable forever' delivery failures."""
    msg = str(getattr(exc, "message", exc)).lower()
    if isinstance(exc, TelegramForbiddenError):
        return _BLOCKED in msg or _DEACTIVATED in msg
    if isinstance(exc, TelegramBadRequest):
        return _CHAT_NOT_FOUND in msg
    return False


async def _deliver(bot: Bot, action: str, chat_id: int, src_chat: int, message_id: int) -> None:
    if action == "forward":
        await bot.forward_message(chat_id, from_chat_id=src_chat, message_id=message_id)
    else:
        await bot.copy_message(chat_id, from_chat_id=src_chat, message_id=message_id)


async def _send(bot: Bot, chat_id: int, text: str) -> Message | None:
    try:
        return await bot.send_message(chat_id, text)
    except Exception:
        return None


async def _edit(bot: Bot, message: Message | None, text: str) -> None:
    if message is None:
        return
    try:
        await bot.edit_message_text(text, chat_id=message.chat.id, message_id=message.message_id)
    except Exception:
        pass


async def fanout(ctx: dict, action: str, chat_id: int, message_id: int, admin_id: int) -> None:
    """Send one message (referenced by ``chat_id``/``message_id`` in the admin's chat) to all users.

    ``action`` is ``"broadcast"`` (copy) or ``"forward"``. Removals are batched and committed once,
    after the loop, so a long send never holds a write transaction open.
    """
    bot: Bot | None = ctx.get("bot")
    sessionmaker = ctx.get("sessionmaker")
    if bot is None or sessionmaker is None:
        logger.warning("fanout: worker missing bot/sessionmaker; skipping")
        return

    async with sessionmaker() as session:
        ids = await UserRepository(session).list_all_ids()

    total = len(ids)
    sent = failed = removed = 0
    to_remove: list[int] = []
    progress = await _send(bot, admin_id, f"📣 Sending to {total} users…")

    for i, uid in enumerate(ids, start=1):
        try:
            await _deliver(bot, action, uid, chat_id, message_id)
            sent += 1
        except TelegramRetryAfter as exc:
            await asyncio.sleep(exc.retry_after)
            try:
                await _deliver(bot, action, uid, chat_id, message_id)
                sent += 1
            except Exception:
                failed += 1
        except (TelegramForbiddenError, TelegramBadRequest) as exc:
            if _should_remove(exc):
                to_remove.append(uid)
                removed += 1
            else:
                failed += 1
        except TelegramAPIError:
            failed += 1  # transient API error → keep the user
        except Exception:
            logger.warning("fanout: unexpected send error (kept user)")
            failed += 1
        if i % 100 == 0:
            await _edit(
                bot, progress, f"📣 {i}/{total} · sent {sent} · failed {failed} · removed {removed}"
            )
        await asyncio.sleep(_SEND_DELAY)

    if to_remove:
        async with sessionmaker() as session:
            repo = UserRepository(session)
            for uid in to_remove:
                await repo.delete(uid)
            await session.commit()

    await _edit(
        bot,
        progress,
        f"✅ Done · {total} users · sent {sent} · failed {failed} · removed {removed}",
    )


async def reset_all_active(ctx: dict, admin_id: int) -> None:
    """Reset panel traffic consumption for every ``active_config`` user (bounded attempt each)."""
    bot: Bot | None = ctx.get("bot")
    sessionmaker = ctx.get("sessionmaker")
    panel = ctx.get("panel")
    if sessionmaker is None or panel is None:
        logger.warning("reset_all_active: worker missing sessionmaker/panel; skipping")
        return

    async with sessionmaker() as session:
        usernames = await UserRepository(session).list_panel_usernames_by_status(
            UserStatus.active_config
        )

    total = len(usernames)
    reset = skipped = 0
    progress = await _send(bot, admin_id, f"♻️ Resetting traffic for {total} active users…")

    for i, username in enumerate(usernames, start=1):
        try:
            panel_user = await panel.get_user(username)
            if panel_user is not None and panel_user.uuid:
                await panel.reset_user_traffic(panel_user.uuid)
                reset += 1
            else:
                skipped += 1
        except RemnawaveError:
            skipped += 1  # bounded single attempt — log via client, skip, move on
        if i % 50 == 0:
            await _edit(bot, progress, f"♻️ {i}/{total} · reset {reset} · skipped {skipped}")
        await asyncio.sleep(0.02)

    await _edit(
        bot, progress, f"✅ Reset done · {total} active · reset {reset} · skipped {skipped}"
    )
