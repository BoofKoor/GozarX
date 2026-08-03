"""Admin API aggregate router — mounted under ``/api`` so endpoints live at ``/api/admin/*``."""

from __future__ import annotations

from fastapi import APIRouter

from gozar.web.routes.admin import (
    auth,
    broadcast,
    buttons,
    dashboard,
    inbox,
    landing,
    settings,
    setup,
    site_content,
    site_devices,
    site_faq,
    site_push,
    site_settings,
    site_setup,
    site_stats,
    system,
    texts,
    users,
)

router = APIRouter(prefix="/admin")
router.include_router(auth.router)
router.include_router(setup.router)
router.include_router(settings.router)
router.include_router(dashboard.router)
router.include_router(texts.router)
router.include_router(buttons.router)
router.include_router(users.router)
router.include_router(broadcast.router)
router.include_router(system.router)
# Website ("site") admin section (P9).
router.include_router(site_setup.router)
router.include_router(site_settings.router)
router.include_router(landing.router)
router.include_router(inbox.router)
router.include_router(site_content.router)
router.include_router(site_devices.router)
router.include_router(site_faq.router)
router.include_router(site_push.router)
router.include_router(site_stats.router)
