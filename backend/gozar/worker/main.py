"""arq worker entrypoint (separate process).

Run: ``python -m gozar.worker.main``

Redis settings are read at runtime inside :func:`run`, never at class-body eval,
so importing this module has no side effects. arq refuses to start with an empty
``functions`` list, so Phase 0 registers a single no-op placeholder; Phase 6
replaces/extends ``functions`` with the real broadcast / forward tasks.
"""

from __future__ import annotations

import logging

from arq import run_worker
from arq.connections import RedisSettings

from gozar.config.logging import configure_logging
from gozar.config.settings import get_settings

logger = logging.getLogger("gozar.worker")


async def noop(ctx: dict) -> None:
    """No-op placeholder so arq has >=1 registered function.

    arq raises "at least one function or cron_job must be registered" when started
    with an empty functions list, so this lets the worker boot and idle. It is never
    enqueued in Phase 0; Phase 6 replaces/extends ``functions`` with the real
    broadcast / forward tasks.
    """
    return None


async def _startup(ctx: dict) -> None:
    logger.info("arq worker started")


async def _shutdown(ctx: dict) -> None:
    logger.info("arq worker stopped")


class WorkerSettings:
    functions = [noop]  # P6 replaces this with broadcast / forward tasks
    cron_jobs: list = []  # P8: nightly pg_dump backup
    on_startup = _startup
    on_shutdown = _shutdown


def run() -> None:
    settings = get_settings()
    configure_logging(settings.log_level, settings.log_json)
    run_worker(WorkerSettings, redis_settings=RedisSettings.from_dsn(settings.redis_url))


if __name__ == "__main__":
    run()
