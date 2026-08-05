"""arq worker entrypoint (separate process).

Run: ``python -m gozar.worker.main``

Redis settings are read at runtime inside :func:`run`, never at class-body eval, so importing this
module has no side effects. ``_startup`` builds the worker's own resources (HTTP client + panel,
DB engine + sessionmaker, aiogram Bot) into the arq ``ctx`` — mirroring the web lifespan and torn
down symmetrically in ``_shutdown``. The Bot is constructed inline (not via the dispatcher) so the
worker never imports the FastAPI/handler graph.
"""

from __future__ import annotations

import logging

import httpx
from aiogram import Bot
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from arq import func, run_worker
from arq.connections import RedisSettings
from arq.cron import cron

from gozar.cache.redis import create_redis_pool
from gozar.config.logging import configure_logging
from gozar.config.settings import get_settings
from gozar.db.session import create_engine, create_sessionmaker
from gozar.remnawave import RemnawaveClient
from gozar.worker.tasks import (
    backup_database,
    broadcast_text,
    fanout,
    reconcile_trials,
    reset_all_active,
    sample_health,
    sample_usage,
    site_push_broadcast,
    site_reconcile,
)

logger = logging.getLogger("gozar.worker")

# A full broadcast to a large audience runs for a long time (100k users at the ~25/s rate ≈ 1h), so
# the fan-out jobs need a much larger ceiling than arq's 300s default — otherwise the job is killed
# mid-send and most users never get the message. max_tries=1 so a failed/interrupted broadcast is
# NEVER auto-retried from the start (that would re-blast everyone already sent) — admin re-triggers.
_BROADCAST_TIMEOUT = 6 * 60 * 60  # 6 hours


async def _startup(ctx: dict) -> None:
    settings = get_settings()
    ctx["http"] = httpx.AsyncClient(timeout=httpx.Timeout(10.0), verify=True)
    ctx["panel"] = RemnawaveClient(ctx["http"], settings.panel_base_url, settings.panel_api_token)
    ctx["engine"] = create_engine(settings.database_url)
    ctx["sessionmaker"] = create_sessionmaker(ctx["engine"])
    # Decoded Redis pool for the health sampler (matches the web app's content/settings cache pool).
    ctx["cache_redis"] = create_redis_pool(settings.redis_url)
    token = settings.bot_token.get_secret_value()
    ctx["bot"] = (
        Bot(token, default=DefaultBotProperties(parse_mode=ParseMode.HTML)) if token else None
    )
    if ctx["bot"] is None:
        logger.warning("worker started without BOT_TOKEN — fan-out tasks will no-op")
    logger.info("arq worker started")


async def _shutdown(ctx: dict) -> None:
    bot = ctx.get("bot")
    if bot is not None:
        await bot.session.close()
    cache_redis = ctx.get("cache_redis")
    if cache_redis is not None:
        await cache_redis.aclose()
    engine = ctx.get("engine")
    if engine is not None:
        await engine.dispose()
    http = ctx.get("http")
    if http is not None:
        await http.aclose()
    logger.info("arq worker stopped")


class WorkerSettings:
    functions = [
        # Long-running fan-out jobs get a large timeout + no auto-retry (see _BROADCAST_TIMEOUT).
        func(fanout, timeout=_BROADCAST_TIMEOUT, max_tries=1),
        func(broadcast_text, timeout=_BROADCAST_TIMEOUT, max_tries=1),
        func(site_push_broadcast, timeout=_BROADCAST_TIMEOUT, max_tries=1),
        # The rest keep arq's defaults (300s timeout, retry) — they're short, bounded per-item work.
        reset_all_active,
        reconcile_trials,
        backup_database,
        sample_health,
        sample_usage,
        site_reconcile,
    ]
    # Nightly DB backup at 03:00 (UTC container clock); a system-health sample every minute
    # (second=0) feeds the monitoring page's history; an hourly usage sample records the traffic
    # and concurrency series nothing else keeps; a trial reconcile sweep every 15 min as the
    # panel-webhook fallback (notify + reset users whose data ran out / trial expired). The site
    # reconcile sweep runs on the same cadence, staggered off the bot's to spread panel load.
    cron_jobs = [
        cron(backup_database, hour=3, minute=0),
        cron(sample_health, second=0),
        # Hourly, on the half hour: the usage series only needs a shape, and staggering
        # it off :00 keeps it out of the way of the reconcile sweeps.
        cron(sample_usage, minute=30),
        cron(reconcile_trials, minute={0, 15, 30, 45}),
        cron(site_reconcile, minute={5, 20, 35, 50}),
    ]
    on_startup = _startup
    on_shutdown = _shutdown


def run() -> None:
    settings = get_settings()
    configure_logging(settings.log_level, settings.log_json)
    run_worker(WorkerSettings, redis_settings=RedisSettings.from_dsn(settings.redis_url))


if __name__ == "__main__":
    run()
