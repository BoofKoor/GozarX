"""Public API aggregate router — mounted under ``/api`` so endpoints live at ``/api/public/*``.

These endpoints are OPEN (no admin JWT). Protection is per-handler: the device-identity cookie plus,
on state-changing routes, Turnstile + a Redis rate limit (P3+). Never gate a public route on
``AdminUser``.
"""

from __future__ import annotations

from fastapi import APIRouter

from gozar.web.routes.public import (
    claim,
    contact,
    device,
    faq,
    pages,
    push,
    rewards,
    site_copy,
    status,
    transfer,
)

router = APIRouter(prefix="/public")
router.include_router(status.router)
router.include_router(claim.router)
router.include_router(rewards.router)
router.include_router(transfer.router)
router.include_router(device.router)
router.include_router(contact.router)
router.include_router(push.router)
router.include_router(pages.router)
router.include_router(faq.router)
router.include_router(site_copy.router)
