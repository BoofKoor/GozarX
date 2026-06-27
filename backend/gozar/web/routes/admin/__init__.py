"""Admin API aggregate router — mounted under ``/api`` so endpoints live at ``/api/admin/*``."""

from __future__ import annotations

from fastapi import APIRouter

from gozar.web.routes.admin import auth, dashboard, settings, setup

router = APIRouter(prefix="/admin")
router.include_router(auth.router)
router.include_router(setup.router)
router.include_router(settings.router)
router.include_router(dashboard.router)
