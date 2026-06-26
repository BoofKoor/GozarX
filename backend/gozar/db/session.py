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
    return create_async_engine(url, pool_pre_ping=True)


def create_sessionmaker(engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(engine, expire_on_commit=False, autoflush=False)
