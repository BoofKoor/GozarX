"""Public API aggregate router — mounted under ``/api`` so endpoints live at ``/api/public/*``.

These endpoints are OPEN (no admin JWT). Protection is per-handler: the device-identity cookie plus,
on state-changing routes, Turnstile + a Redis rate limit (P3+). Never gate a public route on
``AdminUser``.
"""

from __future__ import annotations

from fastapi import APIRouter

from gozar.web.routes.public import claim, status

router = APIRouter(prefix="/public")
router.include_router(status.router)
router.include_router(claim.router)
