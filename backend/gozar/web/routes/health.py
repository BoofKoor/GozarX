"""Liveness/readiness endpoint."""

from __future__ import annotations

from fastapi import APIRouter

router = APIRouter()


@router.get("/health")
async def health() -> dict[str, str]:
    # Extended later to verify DB/Redis readiness; a plain 200 is enough for Phase 0.
    return {"status": "ok"}
