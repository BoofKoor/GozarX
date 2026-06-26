"""FastAPI application factory + lifespan.

No module-level app instance: uvicorn launches this with ``--factory`` so import
has zero side effects. The lifespan is the single place runtime resources are
created and torn down (symmetrically). Phase 0 wires the shared HTTP client to
prove the seam; later phases add the engine, Redis pool, and aiogram bot.
"""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI

from gozar.config.logging import configure_logging
from gozar.config.settings import get_settings
from gozar.db.session import create_engine, create_sessionmaker
from gozar.web.routes import health

logger = logging.getLogger("gozar")


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings = get_settings()
    configure_logging(settings.log_level, settings.log_json)
    logger.info("gozar starting")

    # Shared HTTP client (TLS verification ON) — used by the Remnawave client (P2+).
    app.state.http = httpx.AsyncClient(timeout=httpx.Timeout(10.0), verify=True)

    # Database engine + session factory (lazy pool — no connection until first query).
    app.state.engine = create_engine(settings.database_url)
    app.state.sessionmaker = create_sessionmaker(app.state.engine)

    # Resource seams wired in later phases — create here, tear down symmetrically below:
    #   P2: app.state.redis = await create_redis_pool(settings.redis_url)
    #   P3: app.state.bot, app.state.dp = build_bot_and_dispatcher(settings); await set_webhook(...)
    try:
        yield
    finally:
        #   P3: await app.state.bot.session.close()
        #   P2: await app.state.redis.aclose()
        await app.state.engine.dispose()
        await app.state.http.aclose()
        logger.info("gozar stopped")


def create_app() -> FastAPI:
    app = FastAPI(title="Gozar", version="0.1.0", lifespan=lifespan)
    app.include_router(health.router)
    # Routers added in later phases:
    #   P3: app.include_router(telegram.router)        # POST /tg/{secret}
    #   P5: app.include_router(panel.router)           # POST /panel-webhook
    #   P7: app.include_router(admin_api.router, prefix="/api")
    return app
