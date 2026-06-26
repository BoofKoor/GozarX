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

from gozar.bot.dispatcher import build_bot, build_dispatcher
from gozar.cache.redis import create_redis_pool
from gozar.config.logging import configure_logging
from gozar.config.settings import get_settings
from gozar.db.session import create_engine, create_sessionmaker
from gozar.remnawave import RemnawaveClient
from gozar.web.routes import health, panel, telegram

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

    # Redis (content/settings cache now; aiogram FSM + arq queue later) — lazy pool.
    app.state.redis = create_redis_pool(settings.redis_url)
    # Remnawave panel client over the shared HTTP client (TLS on).
    app.state.panel = RemnawaveClient(
        app.state.http, settings.panel_base_url, settings.panel_api_token
    )

    # aiogram bot + dispatcher (webhook). Skipped without a token; live updates need HTTPS (P9).
    app.state.bot = None
    app.state.dp = None
    token = settings.bot_token.get_secret_value()
    if token:
        app.state.bot = build_bot(token)
        app.state.dp = build_dispatcher(app.state.sessionmaker, app.state.redis, app.state.panel)
        if settings.domain:
            webhook_url = (
                f"https://{settings.domain}/tg/{settings.webhook_secret.get_secret_value()}"
            )
            try:
                await app.state.bot.set_webhook(
                    webhook_url,
                    secret_token=settings.webhook_header_secret.get_secret_value(),
                    drop_pending_updates=True,
                )
                logger.info("telegram webhook registered")
            except Exception:
                logger.exception("failed to register telegram webhook")
        else:
            logger.warning(
                "BOT_TOKEN set but DOMAIN empty — webhook not registered (set in Phase 9)"
            )
    else:
        logger.warning("no BOT_TOKEN — bot disabled (dev)")

    # Resource seams wired in later phases — create here, tear down symmetrically below:
    #   P5: app.state.panel-webhook receiver  ·  P8: arq backup cron
    try:
        yield
    finally:
        if app.state.bot is not None:
            await app.state.bot.session.close()
        await app.state.redis.aclose()
        await app.state.engine.dispose()
        await app.state.http.aclose()
        logger.info("gozar stopped")


def create_app() -> FastAPI:
    app = FastAPI(title="Gozar", version="0.1.0", lifespan=lifespan)
    app.include_router(health.router)
    app.include_router(telegram.router)  # POST /tg/{secret}
    app.include_router(panel.router)  # POST /panel-webhook (Remnawave expiry/limit events)
    # Routers added in later phases:
    #   P7: app.include_router(admin_api.router, prefix="/api")
    return app
