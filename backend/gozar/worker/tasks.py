"""arq worker tasks — bulk fan-out and the nightly DB backup, none of which may run in a handler.

``fanout`` delivers one message to every user (broadcast = ``copy_message``, no "Forwarded from";
forward = ``forward_message``, keeps the header). It removes a user **only** on a genuine permanent
delivery failure (blocked / deactivated / chat-not-found) — never on a transient error (v1 lesson
#4). ``reset_all_active`` zeroes panel traffic consumption for every active user. Both report
progress to the admin's chat and make a single bounded panel/send attempt per user.
``backup_database`` is the arq cron job: it shells out to ``pg_dump``, gzips the dump, and ships it
to the configured Telegram channel — a failed backup is logged and swallowed, never raised.
"""

from __future__ import annotations

import asyncio
import gzip
import json
import logging
import os
from datetime import UTC, datetime

from aiogram import Bot
from aiogram.exceptions import (
    TelegramAPIError,
    TelegramForbiddenError,
    TelegramNotFound,
    TelegramRetryAfter,
)
from aiogram.types import BufferedInputFile, Message
from sqlalchemy.engine import make_url

from gozar.bot.replies import preview_options
from gozar.cache.redis import HEALTH_HISTORY_KEY, HEALTH_HISTORY_MAX
from gozar.config.settings import get_settings
from gozar.db.models.enums import Language, UserStatus
from gozar.db.repositories.config_log import ConfigLogRepository
from gozar.db.repositories.user import UserRepository
from gozar.remnawave import RemnawaveError
from gozar.remnawave.schemas import Subscription
from gozar.services.content import ContentService
from gozar.services.health import build_snapshot, sample_from
from gozar.services.reminders import ReminderService
from gozar.services.settings_service import SettingsService
from gozar.services.trial import TrialService, human_bytes, human_remaining

logger = logging.getLogger("gozar.worker.tasks")

# The ONLY delivery failures that remove a user. Anything else (rate limit, network, 5xx, any other
# Forbidden/NotFound description) is transient → keep the user. aiogram 3 surfaces these as generic
# classes, so we match a substring of `exc.message` (the raw "Forbidden: "/"Not Found: " prefix and
# minor wording shifts don't matter). NB: "chat not found" is a TelegramNotFound, NOT a BadRequest.
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
    if isinstance(exc, TelegramNotFound):
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


async def _broadcast_loop(
    bot: Bot,
    sessionmaker: object,
    admin_id: int,
    send_one: object,
    languages: list[Language] | None = None,
) -> None:
    """Shared fan-out: send to every user via ``send_one(uid)`` (which raises on a failed send),
    applying the strict removal allowlist + throttle + progress. ``languages`` (empty/None ⇒ all)
    narrows the audience for a language-targeted panel broadcast. Removals are batched and committed
    once, after the loop, so a long send never holds a write transaction open.
    """
    async with sessionmaker() as session:  # type: ignore[operator]
        repo = UserRepository(session)
        ids = await (repo.list_ids_by_languages(languages) if languages else repo.list_all_ids())

    total = len(ids)
    sent = failed = removed = 0
    to_remove: list[int] = []
    progress = await _send(bot, admin_id, f"📣 Sending to {total} users…")

    for i, uid in enumerate(ids, start=1):
        try:
            await send_one(uid)  # type: ignore[operator]
            sent += 1
        except TelegramRetryAfter as exc:
            await asyncio.sleep(exc.retry_after)
            try:
                await send_one(uid)  # type: ignore[operator]
                sent += 1
            except Exception:
                failed += 1
        except (TelegramForbiddenError, TelegramNotFound) as exc:
            if _should_remove(exc):
                to_remove.append(uid)
                removed += 1
            else:
                failed += 1
        except TelegramAPIError:
            failed += 1  # transient API error (incl. other BadRequests) → keep the user
        except Exception:
            logger.warning("broadcast: unexpected send error (kept user)")
            failed += 1
        if i % 100 == 0:
            await _edit(
                bot, progress, f"📣 {i}/{total} · sent {sent} · failed {failed} · removed {removed}"
            )
        await asyncio.sleep(_SEND_DELAY)

    if to_remove:
        async with sessionmaker() as session:  # type: ignore[operator]
            repo = UserRepository(session)
            for uid in to_remove:
                await repo.delete(uid)
            await session.commit()

    await _edit(
        bot,
        progress,
        f"✅ Done · {total} users · sent {sent} · failed {failed} · removed {removed}",
    )


async def fanout(ctx: dict, action: str, chat_id: int, message_id: int, admin_id: int) -> None:
    """Copy/forward one message (referenced by ``chat_id``/``message_id`` in the admin's chat) to
    every user. ``action`` is ``"broadcast"`` (copy, no header) or ``"forward"`` — the bot tool.
    """
    bot: Bot | None = ctx.get("bot")
    sessionmaker = ctx.get("sessionmaker")
    if bot is None or sessionmaker is None:
        logger.warning("fanout: worker missing bot/sessionmaker; skipping")
        return

    async def send_one(uid: int) -> None:
        await _deliver(bot, action, uid, chat_id, message_id)

    await _broadcast_loop(bot, sessionmaker, admin_id, send_one)


async def broadcast_text(
    ctx: dict, text: str, admin_id: int, languages: list[str] | None = None
) -> None:
    """Send a composed HTML message to the panel's broadcast audience (it has no source message to
    copy). ``languages`` (empty/None ⇒ everyone) targets specific language groups. Same strict
    removal allowlist as ``fanout``: a user is dropped only on a permanent delivery failure.
    """
    bot: Bot | None = ctx.get("bot")
    sessionmaker = ctx.get("sessionmaker")
    if bot is None or sessionmaker is None:
        logger.warning("broadcast_text: worker missing bot/sessionmaker; skipping")
        return

    valid = {lang.value for lang in Language}
    langs = [Language(c) for c in (languages or []) if c in valid] or None

    async def send_one(uid: int) -> None:
        await bot.send_message(uid, text, parse_mode="HTML")

    await _broadcast_loop(bot, sessionmaker, admin_id, send_one, langs)


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


# ── Trial reconcile sweep (panel-webhook fallback) ────────────────────────────────────────────
def _reconcile_tokens(sub: Subscription) -> dict[str, str]:
    """Reminder tokens built from the live subscription (mirrors the webhook's ``_reminder_tokens``,
    sourced from the panel read instead of the event payload)."""
    return {
        "used_traffic": human_bytes(sub.user.traffic_used_bytes),
        "total_traffic": human_bytes(sub.user.traffic_limit_bytes),
        "expire": human_remaining(sub.user.expires_at),
        "remaining": human_remaining(sub.user.expires_at),
    }


async def reconcile_trials(ctx: dict) -> None:
    """Fallback for the panel webhook: sweep ``active_config`` users and, for any whose live trial
    is TERMINAL (time-expired / disabled / missing), reset them to claimable and send the expiry
    reminder. A data-limited-but-time-valid trial is deliberately left alone (``_is_expired`` is
    False for it) so it stays revivable by a referral bump — the data-limit nudge is webhook-only.

    Idempotent with the webhook — a user it already reset is no longer ``active_config``, so this
    never double-notifies. Best-effort throughout: one bounded panel attempt per user, and a panel
    or send failure for a single user is logged/skipped, never aborting the sweep.
    """
    sessionmaker = ctx.get("sessionmaker")
    panel = ctx.get("panel")
    bot: Bot | None = ctx.get("bot")
    redis = ctx.get("cache_redis")
    if sessionmaker is None or panel is None or redis is None:
        logger.warning("reconcile_trials: worker missing sessionmaker/panel/redis; skipping")
        return

    async with sessionmaker() as session:
        targets = await UserRepository(session).list_active_with_panel()

    healed = 0
    for telegram_id, username in targets:
        try:
            sub, _ = await panel.subscription(username)  # bounded single attempt
        except RemnawaveError:
            continue  # transient — the next sweep retries
        if not TrialService._is_expired(sub):
            continue  # trial still live (incl. data-limited-but-time-valid) — leave it
        tokens = _reconcile_tokens(sub)

        send: tuple[int, str, bool] | None = None
        async with sessionmaker() as session:
            users = UserRepository(session)
            user = await users.get(telegram_id)
            # Skip if it was reset (webhook) or re-claimed (new panel user) since we probed.
            if user is None or user.panel_username != username:
                continue
            service = ReminderService(
                users, ConfigLogRepository(session), SettingsService(session, redis), redis, panel
            )
            outcome = await service.apply_ended_trial(user, tokens)
            if outcome is not None and outcome.user.reminder_enabled:
                msg = await ContentService(session, redis).message(
                    outcome.content_key, outcome.user.language, **outcome.tokens
                )
                send = (outcome.user.telegram_id, msg.text, msg.link_preview)
            await session.commit()

        if send is not None and bot is not None:  # send only AFTER the reset is durable
            try:
                await bot.send_message(
                    send[0], send[1], link_preview_options=preview_options(send[2])
                )
            except Exception:  # blocked user / transient — best-effort, never abort the sweep
                logger.warning("reconcile_trials: reminder send failed (ignored)")
        healed += 1
        await asyncio.sleep(0.02)

    if healed:
        logger.info("reconcile_trials: healed %d ended trial(s)", healed)


# ── Nightly database backup ───────────────────────────────────────────────────────────────────
# pg_dump must match the server's MAJOR version (16); it refuses to dump a newer server. The
# backend image installs postgresql-client-16 for exactly this. Telegram caps bot uploads at 50 MB
# — far above this trial bot's dump for years; an over-cap send simply raises and is logged below.
_PG_DUMP_FLAGS = ("--no-owner", "--no-privileges", "-w")  # -w: never prompt for a password


def _pg_dump_argv_env(database_url: str) -> tuple[list[str], dict[str, str]]:
    """Build the ``pg_dump`` argv + a PGPASSWORD env overlay from a SQLAlchemy URL.

    The password goes through the environment, **never** argv (so it can't leak via ``ps`` or a
    log line). The ``+asyncpg`` driver suffix is irrelevant to libpq and simply ignored here.
    """
    url = make_url(database_url)
    argv = [
        "pg_dump",
        "-h",
        url.host or "localhost",
        "-p",
        str(url.port or 5432),
        "-U",
        url.username or "",
        "-d",
        url.database or "",
        *_PG_DUMP_FLAGS,
    ]
    return argv, {"PGPASSWORD": url.password or ""}


async def _run_pg_dump(argv: list[str], env: dict[str, str]) -> tuple[int, bytes, bytes]:
    """Run pg_dump -> ``(returncode, stdout, stderr)``. Seam: unit tests monkeypatch this."""
    proc = await asyncio.create_subprocess_exec(
        *argv,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        env={**os.environ, **env},
    )
    out, err = await proc.communicate()
    return proc.returncode or 0, out, err


def _backup_chat_id(value: str) -> int | str:
    """A numeric channel id (e.g. ``-100123…``) -> int; otherwise pass through (``@channel``)."""
    v = value.strip()
    return int(v) if v.lstrip("-").isdigit() else v


async def backup_database(ctx: dict) -> None:
    """Dump the database with ``pg_dump``, gzip it, and send it to the backup channel.

    Off until ``BACKUP_CHANNEL_ID`` is set. Every failure (no bot, pg_dump error, send error) is
    logged and swallowed — a backup must never crash the worker or abort the cron schedule.
    """
    settings = get_settings()
    channel = settings.backup_channel_id.strip()
    bot: Bot | None = ctx.get("bot")
    if not channel:
        logger.warning("backup: BACKUP_CHANNEL_ID unset — skipping nightly backup")
        return
    if bot is None:
        logger.warning("backup: worker missing bot — skipping nightly backup")
        return

    argv, env = _pg_dump_argv_env(settings.database_url)
    try:
        code, dump, err = await _run_pg_dump(argv, env)
    except OSError as exc:  # pg_dump binary missing / not executable
        logger.error("backup: could not run pg_dump: %s", exc)
        return
    if code != 0:
        detail = err.decode("utf-8", "replace")[:500]
        logger.error("backup: pg_dump failed (rc=%s): %s", code, detail)
        return

    gz = await asyncio.to_thread(gzip.compress, dump)
    ts = datetime.now(UTC).strftime("%Y%m%d-%H%M%S")
    document = BufferedInputFile(gz, filename=f"gozar-{ts}.sql.gz")
    caption = f"🗄 GozarX DB backup\n{ts} UTC · {len(gz) // 1024} KB"
    try:
        await bot.send_document(_backup_chat_id(channel), document, caption=caption)
        logger.info("backup: sent gozar-%s.sql.gz (%d bytes gz)", ts, len(gz))
    except TelegramAPIError as exc:
        logger.error("backup: send_document failed: %s", exc)


async def sample_health(ctx: dict) -> None:
    """Per-minute system-health sample → a capped Redis list (newest first) for the monitoring page
    history. Best-effort: any failure is logged and swallowed (a missed sample must never abort the
    cron). Builds the same snapshot the live route serves, then keeps only the compact row."""
    redis = ctx.get("cache_redis")
    if redis is None:
        return
    sessionmaker = ctx["sessionmaker"]
    try:
        async with sessionmaker() as session:
            snapshot = await build_snapshot(session, redis, ctx["panel"], ctx.get("bot"))
        await redis.lpush(HEALTH_HISTORY_KEY, json.dumps(sample_from(snapshot)))
        await redis.ltrim(HEALTH_HISTORY_KEY, 0, HEALTH_HISTORY_MAX - 1)
    except Exception:
        logger.warning("health sample failed (ignored)")
