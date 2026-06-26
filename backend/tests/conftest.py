"""Shared test fixtures.

The ``session`` fixture provides a real AsyncSession against ``TEST_DATABASE_URL`` and is
**skipped** when that var is unset, so the default ``pytest`` run needs no database. The schema
is recreated per test (drop_all/create_all) for isolation — cheap for four small tables.
"""

from __future__ import annotations

import os

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from gozar.db import models  # noqa: F401  (register tables on Base.metadata)
from gozar.db.base import Base

TEST_DATABASE_URL = os.environ.get("TEST_DATABASE_URL")


@pytest_asyncio.fixture
async def session():
    if not TEST_DATABASE_URL:
        pytest.skip("TEST_DATABASE_URL not set")
    engine = create_async_engine(TEST_DATABASE_URL)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    sessionmaker = async_sessionmaker(engine, expire_on_commit=False)
    async with sessionmaker() as db:
        yield db
    await engine.dispose()


@pytest_asyncio.fixture
async def db_sessions():
    """A sessionmaker over a fresh schema — for code that opens its own session (middleware)."""
    if not TEST_DATABASE_URL:
        pytest.skip("TEST_DATABASE_URL not set")
    engine = create_async_engine(TEST_DATABASE_URL)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    yield async_sessionmaker(engine, expire_on_commit=False)
    await engine.dispose()
