"""arq worker entrypoint (separate process).

Run: ``python -m gozar.worker.main``

Redis settings are read at runtime inside :func:`run`, never at class-body eval,
so importing this module has no side effects. Phase 0 registers no tasks — the
worker connects to Redis and idles; broadcasts (P6) and the backup cron (P8)
plug into ``WorkerSettings`` later.
"""

from __future__ import annotations

import logging

from arq import run_worker
from arq.connections import RedisSettings

from gozar.config.logging import configure_logging
from gozar.config.settings import get_settings

logger = logging.getLogger("gozar.worker")


async def _startup(ctx: dict) -> None:
    logger.info("arq worker started")


async def _shutdown(ctx: dict) -> None:
    logger.info("arq worker stopped")


class WorkerSettings:
    functions: list = []  # P6: broadcast / forward tasks
    cron_jobs: list = []  # P8: nightly pg_dump backup
    on_startup = _startup
    on_shutdown = _shutdown


def run() -> None:
    settings = get_settings()
    configure_logging(settings.log_level, settings.log_json)
    run_worker(WorkerSettings, redis_settings=RedisSettings.from_dsn(settings.redis_url))


if __name__ == "__main__":
    run()
