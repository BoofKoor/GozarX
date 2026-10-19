"""The worker's side of the console's SSH jobs: ``ops_run`` runs one ``ops_jobs`` row.

The handler wrote the row (``queued``) and the job's password, if it has one, sealed in Redis for
this job alone (``services/ops.hand_over``). Here the row goes ``running``, the password is taken —
and is gone from Redis — the job's body runs (``services/ops_jobs``) while ``bot/progress`` shows
every step in the console message the job took over, and the row is closed ``ok`` or ``failed``
with what the console needs next: the steps, the error's code, a failed install's plan (for 🧹),
the log. The last screen is drawn from the closed row (``bot/ops_view.job_screen``), the same
picture a later redraw gives.

An install records its plan on the row at every step, so a worker that dies half way leaves enough
for 🧹 undo; at the next start (``close_interrupted``) such a row is closed as ``interrupted`` and
its message says so. A job runs ``max_tries=1``: SSH work that half happened is never re-run on its
own.
"""

from __future__ import annotations

import asyncio
import contextlib
import json
import logging
from dataclasses import asdict, is_dataclass
from typing import Any

from aiogram import Bot
from sqlalchemy.ext.asyncio import AsyncSession

from gozar import vault
from gozar.bot import ops_view
from gozar.bot.progress import TelegramReporter
from gozar.bot.screens import ScreenStore
from gozar.db.models.enums import Language
from gozar.db.models.ops import OpsJob, OpsJobStatus, OpsServer
from gozar.db.repositories.ops import OpsJobRepository, OpsServerRepository
from gozar.ops.errors import RemoteError
from gozar.ops.report import Reporter
from gozar.services.button_service import ButtonService
from gozar.services.look import LookService
from gozar.services.ops import take_over
from gozar.services.ops_jobs import BODIES, JobEnv
from gozar.services.settings_service import SettingsService

logger = logging.getLogger("gozar.worker.ops")

VAULT_MISSING = (
    "🔐 VAULT_KEY در ‎.env نیست یا خراب است؛ روی سرور ربات «sudo ./install.sh --secrets» را اجرا کن"
)


def _plan_of(rep: Reporter) -> dict[str, Any] | None:
    plan = rep.context.get("node_plan")
    return asdict(plan) if is_dataclass(plan) and not isinstance(plan, type) else None


async def ops_run(ctx: dict, job_id: str) -> None:
    sessionmaker = ctx["sessionmaker"]
    redis = ctx["cache_redis"]
    bot: Bot | None = ctx.get("bot")
    async with sessionmaker() as session:
        repo = OpsJobRepository(session)
        job = await repo.get(job_id)
        if job is None or job.status != OpsJobStatus.queued:
            return  # closed as stale by the console, or a duplicate delivery
        await repo.start(job)
        await session.commit()
        kind, chat_id, message_id = job.kind, job.chat_id, job.message_id
        look = await LookService(SettingsService(session, redis), redis).snapshot()
    logger.info("ops job %s (%s) started", job_id, kind)

    secret: str | None = None
    vault_error = False
    try:
        secret = await take_over(redis, job_id)
    except vault.VaultError:
        vault_error = True
    except Exception:  # noqa: BLE001 — a job that needs it says so below
        logger.warning("ops job %s: could not read its secret", job_id)

    checkpoint = {"plan": None}

    async def remember_plan(rep: Reporter) -> None:
        """An install's plan, on the row as it changes — what 🧹 needs if this worker dies."""
        plan = _plan_of(rep)
        if plan is None:
            return
        blob = json.dumps(plan, sort_keys=True, ensure_ascii=False)
        if blob == checkpoint["plan"]:
            return
        checkpoint["plan"] = blob
        async with sessionmaker() as s:
            row = await OpsJobRepository(s).get(job_id)
            if row is not None:
                row.result = {**(row.result or {}), "plan": plan}
                await s.commit()

    rep = TelegramReporter(
        bot,
        chat_id,
        message_id,
        look=look,
        looks=LookService(None, redis),
        store=ScreenStore(redis),
        on_change=remember_plan,
    )
    result: dict[str, Any] = {}
    error: str | None = None
    code: str | None = None
    cancelled = False
    async with rep:
        try:
            if vault_error:
                raise RemoteError(VAULT_MISSING, code="vault")
            body = BODIES.get(kind)
            if body is None:
                raise RemoteError(f"کار ناشناخته: {kind}")
            async with sessionmaker() as work:
                row = await OpsJobRepository(work).get(job_id)
                env = JobEnv(
                    job=row,  # type: ignore[arg-type]
                    session=work,
                    http=ctx["http"],
                    panel=ctx["panel"].ops(),
                    rep=rep,
                    secret=secret,
                )
                secret = None  # the body holds the only reference now
                try:
                    result = await body(env)
                finally:
                    env.secret = None
                    # what the body learned stays even when it failed later (a key that is in
                    # now, a key no longer accepted); a broken session just rolls back
                    with contextlib.suppress(Exception):
                        await work.commit()
        except RemoteError as e:
            error, code = e.message, e.code
        except vault.VaultError:
            error, code = VAULT_MISSING, "vault"
        except asyncio.CancelledError:  # the job's time ran out, or the worker is stopping
            cancelled = True
            error = "کار وسط راه متوقف شد (زمانش تمام شد یا worker خاموش شد)"
        except Exception:
            logger.exception("ops job %s failed", job_id)
            error = "خطای داخلی ربات؛ لاگ را ببین"
        finally:
            secret = None

    outcome: dict[str, Any] = {**result, "steps": ops_view.step_rows(rep)}
    if error is not None:
        failed = rep.failed_step()
        outcome.update(code=code, step=failed.key if failed else None)
        plan = _plan_of(rep)
        if plan is not None:
            outcome["plan"] = plan
        outcome["log"] = rep.debug_lines[-ops_view.LOG_LINES :]
    status = OpsJobStatus.interrupted if cancelled else None
    try:
        await _close(ctx, job_id, outcome, error, rep, status=status)
    except Exception:
        logger.warning("ops job %s: could not record its end", job_id, exc_info=True)
    if cancelled:
        raise asyncio.CancelledError
    logger.info("ops job %s (%s) %s", job_id, kind, "failed" if error else "done")


async def _close(
    ctx: dict,
    job_id: str,
    outcome: dict[str, Any],
    error: str | None,
    rep: TelegramReporter,
    *,
    status: str | None = None,
) -> None:
    sessionmaker = ctx["sessionmaker"]
    redis = ctx["cache_redis"]
    async with sessionmaker() as session:
        repo = OpsJobRepository(session)
        job = await repo.get(job_id)
        if job is None:
            return
        await repo.finish(job, ok=error is None, result=outcome, error=error, status=status)
        await session.commit()
        server = await _server_of(session, job)
        buttons = await ButtonService(session, redis).snapshot()
        doc, markup = ops_view.job_screen(job, server=server, lang=_lang(job), buttons=buttons)
    await rep.show(doc, markup)


async def _server_of(session: AsyncSession, job: OpsJob) -> OpsServer | None:
    p = job.params or {}
    sid = p.get("server_id") or (p.get("draft") or {}).get("server_id")
    sid = sid or (job.result or {}).get("server_id")
    if sid is None:
        return None
    return await OpsServerRepository(session).get(int(sid))


def _lang(job: OpsJob) -> Language:
    try:
        return Language(job.lang)
    except ValueError:
        return Language.fa


async def close_interrupted(ctx: dict) -> None:
    """At worker start: a job still ``running`` lost its worker — close it, and say so in its
    message (with 🧹 when an install had started changing things)."""
    sessionmaker = ctx["sessionmaker"]
    redis = ctx["cache_redis"]
    bot: Bot | None = ctx.get("bot")
    try:
        async with sessionmaker() as session:
            rows = await OpsJobRepository(session).fail_interrupted()
            await session.commit()
            for job in rows:
                await session.refresh(job)
            screens = []
            buttons = await ButtonService(session, redis).snapshot()
            look = await LookService(SettingsService(session, redis), redis).snapshot()
            for job in rows:
                server = await _server_of(session, job)
                screens.append(
                    (job, ops_view.job_screen(job, server=server, lang=_lang(job), buttons=buttons))
                )
    except Exception:
        logger.warning("could not close interrupted ops jobs (ignored)", exc_info=True)
        return
    if rows:
        logger.warning("closed %d ops job(s) left running by a dead worker", len(rows))
    for job, (doc, markup) in screens:
        rep = TelegramReporter(
            bot,
            job.chat_id,
            job.message_id,
            look=look,
            looks=LookService(None, redis),
            store=ScreenStore(redis),
        )
        await rep.show(doc, markup)
