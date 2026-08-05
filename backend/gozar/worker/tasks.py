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
import time
from datetime import UTC, datetime

from aiogram import Bot
from aiogram.exceptions import (
    TelegramAPIError,
    TelegramForbiddenError,
    TelegramNotFound,
    TelegramRetryAfter,
)
from aiogram.types import (
    BufferedInputFile,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
)
from sqlalchemy.engine import make_url

from gozar.bot.replies import preview_options
from gozar.cache.redis import HEALTH_HISTORY_KEY, HEALTH_HISTORY_MAX
from gozar.config.settings import get_settings
from gozar.db.models.enums import Language, UserStatus
from gozar.db.models.site_device import SiteDeviceStatus
from gozar.db.repositories.broadcast_log import BroadcastLogRepository
from gozar.db.repositories.config_log import ConfigLogRepository
from gozar.db.repositories.push_subscription import PushSubscriptionRepository
from gozar.db.repositories.site_device import SiteDeviceRepository
from gozar.db.repositories.site_push_log import SitePushLogRepository
from gozar.db.repositories.user import UserRepository
from gozar.remnawave import RemnawaveError
from gozar.remnawave.schemas import PanelUser
from gozar.services import push
from gozar.services.content import ContentService
from gozar.services.health import build_snapshot, sample_from
from gozar.services.reminders import ReminderService
from gozar.services.settings_service import SettingsService
from gozar.services.site_reminders import SiteReminderService, nudge_tokens
from gozar.services.telegram_errors import is_unreachable
from gozar.services.trial import TrialService, human_bytes, human_remaining

logger = logging.getLogger("gozar.worker.tasks")

# The ONLY delivery failures that remove a user. Anything else (rate limit, network, 5xx, any other
# Forbidden/NotFound description) is transient → keep the user. The classification lives in
# services/telegram_errors so the bot's dispatcher error handler decides "permanently unreachable"
# by exactly the same rule this fan-out does.

# Fan-out throughput: send in bounded-concurrency chunks, rate-capped under Telegram's ~30/s
# broadcast ceiling. A fully SEQUENTIAL loop (one awaited send at a time) overlapped nothing, so the
# real throughput was ~5/s — a 100k audience then blew past arq's 300s job timeout at ~1,500 sends
# and the rest never got the message. Sending _CONCURRENCY at once overlaps the per-send network
# latency; the chunk is then paced so the running average stays at _SEND_RATE.
_CONCURRENCY = 20
_SEND_RATE = 25  # messages/second ceiling


def _should_remove(exc: Exception) -> bool:
    """True only for the three permanent 'this user is unreachable forever' delivery failures."""
    return is_unreachable(exc)


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


async def _attempt(send_one: object, uid: int) -> tuple[str, float]:
    """One send attempt mapped to an outcome (never raises): ``('sent',0)`` · ``('flood',retry)`` ·
    ``('remove',0)`` · ``('failed',0)``. The strict removal allowlist (blocked/deactivated/chat-not-
    found only — the v1 mass-deletion lesson) lives here, so a transient failure keeps the user.
    """
    try:
        await send_one(uid)  # type: ignore[operator]
        return ("sent", 0)
    except TelegramRetryAfter as exc:
        return ("flood", exc.retry_after)  # flood control — the caller backs off, then retries once
    except (TelegramForbiddenError, TelegramNotFound) as exc:
        return ("remove", 0) if _should_remove(exc) else ("failed", 0)
    except TelegramAPIError:
        return ("failed", 0)  # transient API error (incl. other BadRequests) → keep the user
    except Exception:
        logger.warning("broadcast: unexpected send error (kept user)")
        return ("failed", 0)


async def _broadcast_loop(
    bot: Bot,
    sessionmaker: object,
    admin_id: int,
    send_one: object,
    languages: list[Language] | None = None,
    *,
    only_active: bool = False,
    only_referrers: bool = False,
    refine: bool = False,
) -> tuple[int, int, int]:
    """Shared fan-out: send to every user via ``send_one(uid)`` (which raises on a failed send),
    applying the strict removal allowlist + a bounded-concurrency, rate-capped throttle + progress.
    ``languages`` (empty/None ⇒ all) narrows the audience for a language-targeted panel broadcast.
    Removals are batched and committed once, after the loop, so a long send never holds a write
    transaction open. See ``_CONCURRENCY``/``_SEND_RATE`` for why this isn't a sequential loop.

    Returns ``(sent, failed, removed)`` so a caller with a log row can record what happened.

    ``refine`` picks the audience query: the panel's broadcast shares ``count_audience`` with the
    endpoint that showed the operator a recipient count, so the number they read before pressing
    send is the number of people this walks. The BOT's own fan-out keeps its historical audience —
    literally every user — because narrowing it here would silently change what ``/admin`` does.
    """
    async with sessionmaker() as session:  # type: ignore[operator]
        repo = UserRepository(session)
        if refine:
            ids = await repo.audience_ids(
                languages, only_active=only_active, only_referrers=only_referrers
            )
        else:
            ids = await (
                repo.list_ids_by_languages(languages) if languages else repo.list_all_ids()
            )

    total = len(ids)
    sent = failed = removed = 0
    to_remove: list[int] = []
    progress = await _send(bot, admin_id, f"📣 Sending to {total} users…")
    last_edit = 0

    for start in range(0, total, _CONCURRENCY):
        chunk = ids[start : start + _CONCURRENCY]
        t0 = time.monotonic()
        results = await asyncio.gather(*[_attempt(send_one, uid) for uid in chunk])

        flooded: list[int] = []
        flood_waits: list[float] = []
        for uid, (tag, wait) in zip(chunk, results, strict=True):
            if tag == "sent":
                sent += 1
            elif tag == "remove":
                to_remove.append(uid)
                removed += 1
            elif tag == "flood":
                flooded.append(uid)
                flood_waits.append(wait)
            else:
                failed += 1

        # A flood-control hit signals to slow the WHOLE broadcast: back off once for the longest
        # requested wait, then retry the flooded users once (a second flood → keep the user).
        if flooded:
            await asyncio.sleep(max(flood_waits))
            for uid in flooded:
                tag, _ = await _attempt(send_one, uid)
                if tag == "sent":
                    sent += 1
                elif tag == "remove":
                    to_remove.append(uid)
                    removed += 1
                else:
                    failed += 1

        done = sent + failed + removed
        if done - last_edit >= 100:
            last_edit = done
            await _edit(
                bot,
                progress,
                f"📣 {done}/{total} · sent {sent} · failed {failed} · removed {removed}",
            )

        # Rate cap: hold each chunk to at least len(chunk)/_SEND_RATE seconds so the running average
        # stays under Telegram's ceiling even though the chunk itself was sent concurrently.
        elapsed = time.monotonic() - t0
        pace = len(chunk) / _SEND_RATE
        if elapsed < pace:
            await asyncio.sleep(pace - elapsed)

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
    return sent, failed, removed


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


def _inline_keyboard(buttons: list[dict] | None) -> InlineKeyboardMarkup | None:
    """The composer's buttons as Telegram's own markup — one per row, which is how a call to action
    under a broadcast reads. A malformed entry is dropped rather than failing the whole send."""
    rows = [
        [InlineKeyboardButton(text=b["text"], url=b["url"])]
        for b in (buttons or [])
        if isinstance(b, dict) and b.get("text") and b.get("url")
    ]
    return InlineKeyboardMarkup(inline_keyboard=rows) if rows else None


async def broadcast_text(
    ctx: dict,
    text: str,
    admin_id: int,
    languages: list[str] | None = None,
    only_active: bool = False,
    only_referrers: bool = False,
    buttons: list[dict] | None = None,
    log_id: int | None = None,
) -> None:
    """Send a composed HTML message to the panel's broadcast audience (it has no source message to
    copy). ``languages`` (empty/None ⇒ everyone) targets specific language groups, and the two
    ``only_*`` flags narrow it further — the same query the endpoint counted with. Same strict
    removal allowlist as ``fanout``: a user is dropped only on a permanent delivery failure.

    ``log_id`` points at the ``broadcast_logs`` row written when the job was enqueued; the outcome
    is written back into it so the history can say what happened rather than only that it started.
    """
    bot: Bot | None = ctx.get("bot")
    sessionmaker = ctx.get("sessionmaker")
    if bot is None or sessionmaker is None:
        logger.warning("broadcast_text: worker missing bot/sessionmaker; skipping")
        await _finish_broadcast_log(sessionmaker, log_id, 0, 0, 0, ok=False)
        return

    valid = {lang.value for lang in Language}
    langs = [Language(c) for c in (languages or []) if c in valid] or None
    markup = _inline_keyboard(buttons)

    async def send_one(uid: int) -> None:
        await bot.send_message(uid, text, parse_mode="HTML", reply_markup=markup)

    await _mark_broadcast_sending(sessionmaker, log_id)
    try:
        sent, failed, removed = await _broadcast_loop(
            bot,
            sessionmaker,
            admin_id,
            send_one,
            langs,
            only_active=only_active,
            only_referrers=only_referrers,
            refine=True,
        )
    except Exception:
        # The fan-out could not run at all. Recording that is the whole point of the row: without
        # it the history would sit on "sending" forever and look like a job still in flight.
        logger.exception("broadcast_text: fan-out failed")
        await _finish_broadcast_log(sessionmaker, log_id, 0, 0, 0, ok=False)
        raise
    await _finish_broadcast_log(sessionmaker, log_id, sent, failed, removed)


async def _mark_broadcast_sending(sessionmaker: object, log_id: int | None) -> None:
    if sessionmaker is None or log_id is None:
        return
    async with sessionmaker() as session:  # type: ignore[operator]
        await BroadcastLogRepository(session).mark_sending(log_id)
        await session.commit()


async def _finish_broadcast_log(
    sessionmaker: object,
    log_id: int | None,
    sent: int,
    failed: int,
    removed: int,
    *,
    ok: bool = True,
) -> None:
    """Bookkeeping must never take the broadcast down with it — the messages already went out."""
    if sessionmaker is None or log_id is None:
        return
    try:
        async with sessionmaker() as session:  # type: ignore[operator]
            await BroadcastLogRepository(session).complete(
                log_id, sent=sent, failed=failed, removed=removed, ok=ok
            )
            await session.commit()
    except Exception:
        logger.warning("broadcast_text: could not record outcome for log %s", log_id)


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
def _reconcile_tokens(user: PanelUser) -> dict[str, str]:
    """Reminder tokens built from the authoritative user record (mirrors the webhook's
    ``_reminder_tokens`` — the webhook payload is the SAME ``GetFullUserResponseModel`` shape)."""
    return {
        "used_traffic": human_bytes(user.traffic.used_bytes),
        "total_traffic": human_bytes(user.traffic_limit_bytes),
        "expire": human_remaining(user.expire_at),
        "remaining": human_remaining(user.expire_at),
    }


async def reconcile_trials(ctx: dict) -> None:
    """Fallback for the panel webhook: sweep ``active_config`` users and, for any whose panel
    account is TERMINAL (time-expired / disabled / missing), reset them to claimable and send the
    expiry reminder. A data-limited-but-time-valid trial is deliberately left alone
    (``_panel_user_terminal`` is False for it) so it stays revivable by a referral bump — the
    data-limit nudge is webhook-only.

    Each user is probed with a single ``get_user`` (the authoritative user record), NOT
    ``subscription``: a terminal trial has no active links, so the subscription path falls through
    to the raw-config endpoint whose failure would raise and silently skip the user every sweep —
    the exact reason expired accounts piled up. The user record is one call, needs no links, and its
    ``status`` is the source of truth (and a 404 means it's already gone → still reset the user).

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
            # Authoritative user record (single call, no link resolution): its `status` is the
            # source of truth and it never falls through to the raw-config endpoint the way
            # `subscription()` does for a link-less expired user (which would raise and skip it).
            panel_user = await panel.get_user(username)  # None on 404 — the account is already gone
        except RemnawaveError:
            continue  # transient — the next sweep retries
        # A 404 (already deleted in the panel) is terminal too: reset the still-active_config user.
        if panel_user is not None and not TrialService._panel_user_terminal(panel_user):
            continue  # trial still live (incl. data-limited-but-time-valid) — leave it
        tokens = _reconcile_tokens(panel_user) if panel_user is not None else {}

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


# ── Site Web Push: broadcast + reconcile sweep ────────────────────────────────────────────────
async def site_push_broadcast(
    ctx: dict,
    title: str,
    body: str,
    url: str = "",
    locale: str | None = None,
    log_id: int | None = None,
) -> None:
    """Fan a Web Push out to the ACTIVE site subscriptions (admin-composed copy).

    Prunes a subscription ONLY on a 404/410 from the push service (never on a transient error — the
    v1 mass-deletion lesson). Bulk push runs in the worker, never in a handler.

    ``locale`` narrows the audience to one language. ``log_id`` points at the ``site_push_logs`` row
    the route created; the outcome is written back to it so the admin can actually see whether the
    broadcast landed — this used to be a stderr line and nothing else.
    """
    sessionmaker = ctx.get("sessionmaker")
    if sessionmaker is None:
        logger.warning("site_push_broadcast: worker missing sessionmaker; skipping")
        return

    payload = json.dumps({"title": title, "body": body, "url": url})
    async with sessionmaker() as session:
        subs = await PushSubscriptionRepository(session).list_active(locale)
        jobs = [(s.endpoint, push.subscription_info(s)) for s in subs]
        if log_id is not None:
            await SitePushLogRepository(session).mark_sending(log_id)
            await session.commit()

    sent = failed = 0
    gone: list[str] = []
    for endpoint, info in jobs:
        outcome = await push.send_push(info, payload)
        if outcome is push.PushOutcome.SENT:
            sent += 1
        elif outcome is push.PushOutcome.GONE:
            gone.append(endpoint)
        else:
            failed += 1
        await asyncio.sleep(push.PUSH_SEND_DELAY)

    if gone:
        async with sessionmaker() as session:
            repo = PushSubscriptionRepository(session)
            for endpoint in gone:
                await repo.deactivate(endpoint)
            await session.commit()
    if log_id is not None:
        async with sessionmaker() as session:
            await SitePushLogRepository(session).complete(
                log_id, sent=sent, failed=failed, pruned=len(gone)
            )
            await session.commit()
    logger.info(
        "site_push_broadcast: sent %d · failed %d · pruned %d (of %d)",
        sent,
        failed,
        len(gone),
        len(jobs),
    )


async def site_reconcile(ctx: dict) -> None:
    """Site fallback for the panel webhook: sweep ``active_config`` devices and self-heal any whose
    panel trial is TERMINAL (time-expired / disabled / missing) — reset to claimable + push an
    'ended' nudge. A data-limited-but-time-valid trial is deliberately left alone (revivable by a
    referral/reward bump; the data-limit nudge is webhook-only, mirroring the bot).

    Single bounded ``get_user`` per device (the authoritative record, NOT ``subscription`` — a
    terminal trial has no links and would fall through to the raw-config endpoint and mask the
    expiry). Idempotent with the webhook: a device it already reset is no longer ``active_config``,
    and it re-verifies the row is unchanged since the probe before mutating.
    """
    sessionmaker = ctx.get("sessionmaker")
    panel = ctx.get("panel")
    redis = ctx.get("cache_redis")
    if sessionmaker is None or panel is None or redis is None:
        logger.warning("site_reconcile: worker missing sessionmaker/panel/redis; skipping")
        return

    async with sessionmaker() as session:
        targets = await SiteDeviceRepository(session).list_active_with_panel()

    healed = 0
    for uuid, username in targets:
        try:
            panel_user = await panel.get_user(username)  # None on 404 — the account is already gone
        except RemnawaveError:
            continue  # transient — the next sweep retries (single bounded call, never a loop)
        if panel_user is not None and not TrialService._panel_user_terminal(panel_user):
            continue  # trial still live (incl. data-limited-but-time-valid) — leave it
        tokens = nudge_tokens(panel_user) if panel_user is not None else {}

        nudge = None
        async with sessionmaker() as session:
            devices = SiteDeviceRepository(session)
            device = await devices.get(uuid)
            # Skip if it was reset (webhook) or re-claimed (new panel user) since we probed.
            if (
                device is None
                or device.site_panel_username != username
                or device.status != SiteDeviceStatus.active_config
            ):
                continue
            service = SiteReminderService(devices, SettingsService(session, redis), redis, panel)
            nudge = await service.apply_ended_trial(device, tokens)
            await session.commit()

        if nudge is not None:  # push only AFTER the reset is durable
            await push.deliver_device_push(
                sessionmaker,
                redis,
                nudge.device_uuid,
                title_key=nudge.title_key,
                body_key=nudge.body_key,
                url="/",
                tokens=nudge.tokens,
            )
        healed += 1
        await asyncio.sleep(0.02)

    if healed:
        logger.info("site_reconcile: healed %d ended trial(s)", healed)


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
