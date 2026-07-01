"""Async engine + session-factory builders.

Zero import side effects: these are factories, not module-level instances, and the asyncpg pool is
lazy (no connection is opened until the first query). The FastAPI lifespan builds one engine +
sessionmaker per process and stores them on ``app.state``.
"""

from __future__ import annotations

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)


def create_engine(url: str) -> AsyncEngine:
    # Pin the connection time zone to UTC so date-truncation aggregates (the dashboard's per-day
    # buckets in ConfigLogRepository.daily_counts / UserRepository.signups_daily) group by UTC day
    # regardless of the Postgres server's configured TimeZone — asyncpg forwards this as a libpq
    # session setting. Applied only for asyncpg URLs so other drivers (tests) are untouched.
    connect_args: dict = {}
    if "asyncpg" in url:
        connect_args["server_settings"] = {"timezone": "UTC"}
    return create_async_engine(url, pool_pre_ping=True, connect_args=connect_args)


def create_sessionmaker(engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(engine, expire_on_commit=False, autoflush=False)
