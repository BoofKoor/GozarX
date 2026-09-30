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
from gozar.cache.redis import HEALTH_HISTORY_KEY, HEALTH_HISTORY_MAX, single_flight
from gozar.config.settings import get_settings
from gozar.db.models.enums import Language, UserStatus
from gozar.db.models.site_device import SiteDeviceStatus
from gozar.db.repositories.broadcast_log import BroadcastLogRepository
from gozar.db.repositories.config_log import ConfigLogRepository
from gozar.db.repositories.push_subscription import PushSubscriptionRepository
from gozar.db.repositories.site_device import SiteDeviceRepository
from gozar.db.repositories.site_push_log import SitePushLogRepository
from gozar.db.repositories.usage_sample import UsageSampleRepository
from gozar.db.repositories.user import UserRepository
from gozar.remnawave import RemnawaveError
from gozar.remnawave.schemas import PanelUser
from gozar.services import push
from gozar.services.content import ContentService
from gozar.services.health import build_snapshot, sample_from
from gozar.services.panel_cache import write_squad_online
from gozar.services.reminders import ReminderService
from gozar.services.settings_service import SettingKey, SettingsService, SiteSettingKey
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
#: How often a logged broadcast writes its running counts back to its row (sends between writes).
_CHECKPOINT_EVERY = 500


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
    progress: dict[str, int] | None = None,
    on_start: object | None = None,
    on_checkpoint: object | None = None,
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

    ``progress`` (if given) holds the running ``sent``/``failed``/``removed`` counts as they
    change, so a caller whose job is CANCELLED mid-send — a worker restart, which every deploy is —
    can still record how far it got. ``on_start(total)`` and ``on_checkpoint()`` are awaited once
    the audience is known and every few hundred sends, for callers that persist those counts.
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
    counts = progress if progress is not None else {}
    counts.update(sent=0, failed=0, removed=0)
    if on_start is not None:
        await on_start(total)  # type: ignore[operator]
    progress_msg = await _send(bot, admin_id, f"📣 Sending to {total} users…")
    last_edit = 0
    last_checkpoint = 0

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
        counts.update(sent=sent, failed=failed, removed=removed)
        if done - last_edit >= 100:
            last_edit = done
            await _edit(
                bot,
                progress_msg,
                f"📣 {done}/{total} · sent {sent} · failed {failed} · removed {removed}",
            )
        if on_checkpoint is not None and done - last_checkpoint >= _CHECKPOINT_EVERY:
            last_checkpoint = done
            await on_checkpoint()  # type: ignore[operator]

        # Rate cap: hold each chunk to at least len(chunk)/_SEND_RATE seconds so the running average
        # stays under Telegram's ceiling even though the chunk itself was sent concurrently.
        elapsed = time.monotonic() - t0
        pace = len(chunk) / _SEND_RATE
        if elapsed < pace:
            await asyncio.sleep(pace - elapsed)

    if to_remove:
        # MARKED, never deleted: a delete cascaded the user's claim history away (every past day's
        # figures shrank after each broadcast) and orphaned their live panel account, which only the
        # row can map back for the expiry cleanup. Marked, they leave every audience instead.
        async with sessionmaker() as session:  # type: ignore[operator]
            await UserRepository(session).mark_unreachable(to_remove, datetime.now(UTC))
            await session.commit()

    await _edit(
        bot,
        progress_msg,
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

    counts: dict[str, int] = {}

    async def started(total: int) -> None:
        await _mark_broadcast_sending(sessionmaker, log_id, recipients=total)

    async def checkpoint() -> None:
        await _record_broadcast_progress(sessionmaker, log_id, counts)

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
            progress=counts,
            on_start=started,
            on_checkpoint=checkpoint,
        )
    except BaseException:
        # BaseException, not Exception: a worker restart CANCELS the job (CancelledError is not an
        # Exception), and every deploy restarts the worker. Catching only Exception left the row on
        # "sending" with 0/0/0 forever, so nobody could tell how many of the audience got it. The
        # counts reached so far are what gets recorded; the job is never re-run (max_tries=1).
        logger.warning("broadcast_text: fan-out stopped before finishing")
        await _finish_broadcast_log(
            sessionmaker,
            log_id,
            counts.get("sent", 0),
            counts.get("failed", 0),
            counts.get("removed", 0),
            ok=False,
        )
        raise
    await _finish_broadcast_log(sessionmaker, log_id, sent, failed, removed)


async def _mark_broadcast_sending(
    sessionmaker: object, log_id: int | None, *, recipients: int | None = None
) -> None:
    if sessionmaker is None or log_id is None:
        return
    async with sessionmaker() as session:  # type: ignore[operator]
        await BroadcastLogRepository(session).mark_sending(log_id, recipients=recipients)
        await session.commit()


async def _record_broadcast_progress(
    sessionmaker: object, log_id: int | None, counts: dict[str, int]
) -> None:
    """Best-effort: a bookkeeping write must never take the broadcast down with it."""
    if sessionmaker is None or log_id is None:
        return
    try:
        async with sessionmaker() as session:  # type: ignore[operator]
            await BroadcastLogRepository(session).record_progress(
                log_id,
                sent=counts.get("sent", 0),
                failed=counts.get("failed", 0),
                removed=counts.get("removed", 0),
            )
            await session.commit()
    except Exception:
        logger.warning("broadcast_text: could not record progress for log %s", log_id)


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
            if panel_user is not None and panel_user.ref:  # uuid on panel 2.x, numeric id on 3.x
                await panel.reset_user_traffic(panel_user.ref)
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


#: Consecutive panel failures after which a pending-revoke pass stops: a panel that is down fails
#: every attempt, and each one costs a full request timeout the trial sweep behind it is waiting on.
_REVOKE_FAILURES_BEFORE_STOP = 3


async def _finish_pending_revokes(
    sessionmaker: object,
    panel: object,
    list_pending: object,
    clear: object,
) -> int:
    """Delete the panel accounts a ban/block could not reach at the time; returns how many landed.

    A ban keeps the user's panel handle when the delete fails — forgetting it made the account
    impossible to revoke ever, since nothing maps a panel user back to a row without it. This is the
    retry that the admin panel's "revoke pending" warning promises: one bounded attempt per account
    per sweep, never a loop. ``clear(session, key, username)`` re-checks the row under a fresh
    session and drops the handle only if it is still the same pending revoke.
    """
    async with sessionmaker() as session:  # type: ignore[operator]
        pending = await list_pending(session)  # type: ignore[operator]
    done = failures = 0
    for key, username in pending:
        try:
            await panel.delete_user_by_username(username)  # type: ignore[attr-defined]
        except RemnawaveError:
            failures += 1
            if failures >= _REVOKE_FAILURES_BEFORE_STOP:
                logger.warning("pending revokes: panel unreachable; the next sweep retries")
                break
            continue
        failures = 0
        async with sessionmaker() as session:  # type: ignore[operator]
            if await clear(session, key, username):  # type: ignore[operator]
                await session.commit()
                done += 1
    return done


async def _list_user_revokes(session: object) -> list[tuple[int, str]]:
    return await UserRepository(session).list_revoke_pending()  # type: ignore[arg-type]


async def _clear_user_revoke(session: object, telegram_id: int, username: str) -> bool:
    user = await UserRepository(session).get(telegram_id)  # type: ignore[arg-type]
    if user is None or user.status is not UserStatus.banned or user.panel_username != username:
        return False
    user.panel_username = None
    return True


async def _list_device_revokes(session: object) -> list[tuple[str, str]]:
    return await SiteDeviceRepository(session).list_revoke_pending()  # type: ignore[arg-type]


async def _clear_device_revoke(session: object, uuid: str, username: str) -> bool:
    device = await SiteDeviceRepository(session).get(uuid)  # type: ignore[arg-type]
    if (
        device is None
        or device.status != SiteDeviceStatus.blocked
        or device.site_panel_username != username
    ):
        return False
    device.site_panel_username = None
    return True


#: How long one reconcile run may spend probing, and at most how many trials it probes. arq kills a
#: job at 300 s, and one bounded ``get_user`` per active trial for the live install's ~10,000 took
#: far longer — every run died partway and the next started from the top again, so the trials at the
#: end of the list were NEVER checked: no expiry reminder, and "active configs" never came down.
_RECONCILE_BUDGET_SECONDS = 240.0
_RECONCILE_MAX_PER_RUN = 5_000
#: Where the last run stopped, per sweep; the next run resumes after it and wraps at the end.
_RECONCILE_CURSOR_KEY = "reconcile:cursor:{sweep}"
_RECONCILE_CURSOR_TTL = 24 * 3600


def _resume_order(targets: list[tuple], cursor: str | None, *, numeric: bool) -> list[tuple]:
    """``targets`` sorted by key, rotated to start just after ``cursor`` (a full pass ends back at
    the start). A cursor that no longer matches anything simply starts from the top."""
    ordered = sorted(targets, key=lambda t: t[0])
    if cursor is None:
        return ordered
    try:
        after = int(cursor) if numeric else cursor
    except ValueError:
        return ordered
    split = next((i for i, t in enumerate(ordered) if t[0] > after), len(ordered))
    return ordered[split:] + ordered[:split]


class _SweepBudget:
    """Stops a sweep before arq does, and remembers where — so the NEXT run carries on."""

    def __init__(self, redis: object, sweep: str) -> None:
        self._redis = redis
        self._key = _RECONCILE_CURSOR_KEY.format(sweep=sweep)
        self._deadline = time.monotonic() + _RECONCILE_BUDGET_SECONDS
        self._done = 0

    async def cursor(self) -> str | None:
        raw = await self._redis.get(self._key)  # type: ignore[attr-defined]
        return raw.decode() if isinstance(raw, bytes) else raw

    def spent(self) -> bool:
        return self._done >= _RECONCILE_MAX_PER_RUN or time.monotonic() >= self._deadline

    def tick(self) -> None:
        self._done += 1

    async def stop_after(self, key: object) -> None:
        await self._redis.set(self._key, str(key), ex=_RECONCILE_CURSOR_TTL)  # type: ignore[attr-defined]

    async def finished(self) -> None:
        await self._redis.delete(self._key)  # type: ignore[attr-defined]


async def reconcile_trials(ctx: dict) -> None:
    """Fallback for the panel webhook: sweep ``active_config`` users and, for any whose panel
    account is TERMINAL (time-expired / disabled / missing), reset them to claimable and send the
    expiry reminder. A data-limited-but-time-valid trial is deliberately left alone
    (``_panel_user_terminal`` is False for it) so it stays revivable by a referral bump — the
    data-limit nudge is webhook-only.

    Each user is probed with a single ``get_user`` (the authoritative user record), NOT
    ``subscription``: the user record is one call that resolves no hosts into links — the sweep
    has no use for them — and its ``status`` is the source of truth (and a 404 means it's already
    gone → still reset the user).

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

    revoked = await _finish_pending_revokes(
        sessionmaker, panel, _list_user_revokes, _clear_user_revoke
    )
    if revoked:
        logger.info("reconcile_trials: finished %d pending ban revoke(s)", revoked)

    async with sessionmaker() as session:
        targets = await UserRepository(session).list_active_with_panel()

    budget = _SweepBudget(redis, "bot")
    ordered = _resume_order(targets, await budget.cursor(), numeric=True)
    healed = 0
    last: int | None = None
    for telegram_id, username in ordered:
        if budget.spent():
            await budget.stop_after(last)
            logger.info("reconcile_trials: budget spent; the next run resumes after %s", last)
            break
        budget.tick()
        last = telegram_id
        try:
            # Authoritative user record (single call, no link resolution): its `status` is the
            # source of truth for whether the trial has ended.
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
            if (
                outcome is not None
                and outcome.user.reminder_enabled
                and outcome.user.unreachable_at is None  # the chat is gone; the send would fail
            ):
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

    else:
        await budget.finished()  # a full pass: the next run starts from the top

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
            # The audience actually walked, not the count taken at enqueue: subscriptions come and
            # go in between, and "delivered" read above 100%.
            await SitePushLogRepository(session).mark_sending(log_id, recipients=len(jobs))
            await session.commit()

    sent = failed = 0
    gone: list[str] = []
    ok = False
    try:
        for endpoint, info in jobs:
            outcome = await push.send_push(info, payload)
            if outcome is push.PushOutcome.SENT:
                sent += 1
            elif outcome is push.PushOutcome.GONE:
                gone.append(endpoint)
            else:
                failed += 1
            await asyncio.sleep(push.PUSH_SEND_DELAY)
        ok = True
    finally:
        # Whatever stopped the loop — the job's own timeout, a worker restart (a CancelledError,
        # which `except Exception` never sees), a crash — the row says how far it got. It used to
        # stay on "sending" forever and the history polled it every five seconds.
        if gone:
            async with sessionmaker() as session:
                repo = PushSubscriptionRepository(session)
                for endpoint in gone:
                    await repo.deactivate(endpoint)
                await session.commit()
        if log_id is not None:
            async with sessionmaker() as session:
                await SitePushLogRepository(session).complete(
                    log_id, sent=sent, failed=failed, pruned=len(gone), ok=ok
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

    Single bounded ``get_user`` per device (the authoritative record, NOT ``subscription`` — one
    call, no host-to-link resolution, and its ``status`` is the source of truth). Idempotent with
    the webhook: a device it already reset is no longer ``active_config``, and it re-verifies the
    row is unchanged since the probe before mutating.
    """
    sessionmaker = ctx.get("sessionmaker")
    panel = ctx.get("panel")
    redis = ctx.get("cache_redis")
    if sessionmaker is None or panel is None or redis is None:
        logger.warning("site_reconcile: worker missing sessionmaker/panel/redis; skipping")
        return

    revoked = await _finish_pending_revokes(
        sessionmaker, panel, _list_device_revokes, _clear_device_revoke
    )
    if revoked:
        logger.info("site_reconcile: finished %d pending block revoke(s)", revoked)

    async with sessionmaker() as session:
        targets = await SiteDeviceRepository(session).list_active_with_panel()

    budget = _SweepBudget(redis, "site")
    ordered = _resume_order(targets, await budget.cursor(), numeric=False)
    healed = 0
    last: str | None = None
    for uuid, username in ordered:
        if budget.spent():
            await budget.stop_after(last)
            logger.info("site_reconcile: budget spent; the next run resumes after %s", last)
            break
        budget.tick()
        last = uuid
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

    else:
        await budget.finished()

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


async def sample_usage(ctx: dict) -> None:
    """Hourly snapshot of what the service is carrying → ``usage_samples``.

    The panel only ever reports a cumulative lifetime byte counter and a live concurrency reading,
    so without this row nothing anywhere records what last Tuesday looked like — and a history that
    was never written down cannot be reconstructed afterwards.

    Durable, unlike ``sample_health``, which keeps its series in a capped Redis list: this one is
    the record, and a restart or an eviction must not be able to erase it.

    The reading is stored exactly as the panel gave it. Differencing happens at read time, which is
    what keeps a counter reset detectable rather than silently absorbed.

    Best-effort, like every sampler here: an unreachable panel skips one hour, and a skipped hour
    only widens one gap. Recording nothing is strictly better than recording a zero, which would
    read as "we carried no traffic" and drag every average down with it.
    """
    stats = await ctx["panel"].system_stats()
    if stats is None:
        logger.warning("usage sample skipped: panel did not answer")
        return
    if not stats.traffic_known:
        # Stored as 0 it would read as a counter reset, and the next real reading would then count
        # the whole lifetime total as one hour's traffic. A skipped hour only widens one gap.
        logger.warning("usage sample skipped: the panel sent no traffic counter")
        return
    try:
        async with ctx["sessionmaker"]() as session:
            await UsageSampleRepository(session).record(
                total_bytes=stats.total_traffic_bytes,
                online_now=stats.online_now,
                nodes_online=stats.nodes_online,
                mem_used=stats.mem_used,
                mem_total=stats.mem_total,
            )
            await session.commit()
    except Exception:
        logger.warning("usage sample failed (ignored)")


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
            snapshot = await build_snapshot(
                session, redis, ctx["panel"], ctx.get("bot"), fresh=True
            )
        await redis.lpush(HEALTH_HISTORY_KEY, json.dumps(sample_from(snapshot)))
        await redis.ltrim(HEALTH_HISTORY_KEY, 0, HEALTH_HISTORY_MAX - 1)
    except Exception:
        logger.warning("health sample failed (ignored)")


async def refresh_squad_online(ctx: dict) -> None:
    """Count the trial squad(s)' online users and record the figure for the dashboard.

    This is the sweep ``/dashboard/stats`` used to run inline — every panel user, 500 per request,
    one request after another. It runs HERE, queued by the dashboard when its recorded figure goes
    stale, so it happens at most once at a time (the job id is fixed, and the lock below covers a
    second worker) and only while somebody is looking. A failed sweep records nothing: the previous
    figure keeps being served until it expires, which beats swapping in a panel-wide number that
    counts the operator's own squads.
    """
    redis = ctx.get("cache_redis")
    panel = ctx.get("panel")
    sessionmaker = ctx.get("sessionmaker")
    if redis is None or panel is None or sessionmaker is None:
        return
    async with single_flight(redis, "squad_online", "sweep", ttl_seconds=300) as first:
        if not first:
            return
        async with sessionmaker() as session:
            settings = SettingsService(session, redis)
            squads = {
                s
                for s in (
                    await settings.get(SettingKey.TRIAL_SQUAD),
                    await settings.get(SiteSettingKey.SITE_TRIAL_SQUAD),
                )
                if s
            }
        if not squads:
            return
        activity = await panel.squad_online_count(squads)
        if activity is not None:
            await write_squad_online(redis, activity.online, activity.week)
