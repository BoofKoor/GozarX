"""System monitoring (auth-gated): a live health snapshot + the recent history series.

``/health`` builds a fresh snapshot on each request (DB/Redis pings, the Telegram webhook state +
latency, the panel, and host resources) — see ``services/health.py``. ``/history`` returns the
per-minute samples the worker has stored in Redis (newest-first list, capped ~24h), oldest-first for
charting. Both are cheap and read-only.
"""

from __future__ import annotations

import json
import logging

from fastapi import APIRouter, Query, Request

from gozar.cache.redis import HEALTH_HISTORY_KEY
from gozar.services.health import HealthSnapshot, HistoryRow, build_snapshot
from gozar.web.dependencies import AdminUser, DbSession

logger = logging.getLogger("gozar.web.system")

router = APIRouter(prefix="/system", tags=["system"])

_MAX_HISTORY = 1440


@router.get("/health", response_model=HealthSnapshot)
async def system_health(request: Request, session: DbSession, admin: AdminUser) -> HealthSnapshot:
    return await build_snapshot(
        session,
        request.app.state.redis,
        request.app.state.panel,
        getattr(request.app.state, "bot", None),
    )


@router.get("/history", response_model=list[HistoryRow])
async def system_history(
    request: Request, admin: AdminUser, minutes: int = Query(default=60)
) -> list[HistoryRow]:
    count = max(1, min(minutes, _MAX_HISTORY))
    raw = await request.app.state.redis.lrange(HEALTH_HISTORY_KEY, 0, count - 1)
    rows: list[HistoryRow] = []
    for item in reversed(raw):  # stored newest-first -> return oldest-first for the chart
        try:
            rows.append(HistoryRow.model_validate(json.loads(item)))
        except (ValueError, TypeError):
            continue  # skip a malformed sample rather than failing the whole series
    return rows
