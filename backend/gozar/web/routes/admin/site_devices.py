"""Website device browser (auth-gated) — search, inspect and moderate ``site_devices``.

The website's users were entirely invisible to the panel: no list, no lookup, no actions. The
anti-abuse analytics reported "N devices share a fingerprint" and "these IP buckets hold several
devices" while giving no way to see WHICH devices or to do anything about them.

Every mutation goes through ``SiteAdminService`` so the logic stays out of the delivery layer.
Actions are block / unblock / reset-trial — all reversible. There is deliberately no hard delete
here: ``blocked`` keeps the anti-abuse trail that made the device worth looking at.
"""

from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, HTTPException, Query, Request
from pydantic import BaseModel

from gozar.db.models.site_device import SiteDevice, SiteDeviceStatus
from gozar.db.repositories.site_claim import SiteClaimRepository
from gozar.db.repositories.site_device import SiteDeviceRepository
from gozar.db.repositories.site_reward import SiteRewardRepository
from gozar.services.site_admin import SiteAdminService
from gozar.web.dependencies import AdminUser, DbSession

router = APIRouter(prefix="/site/devices", tags=["site-devices"])

_STATUSES = {
    SiteDeviceStatus.available,
    SiteDeviceStatus.active_config,
    SiteDeviceStatus.blocked,
}


def _service(request: Request, session: object) -> SiteAdminService:
    return SiteAdminService(
        SiteDeviceRepository(session),  # type: ignore[arg-type]
        SiteClaimRepository(session),  # type: ignore[arg-type]
        SiteRewardRepository(session),  # type: ignore[arg-type]
        request.app.state.panel,
        request.app.state.redis,
    )


class DeviceOut(BaseModel):
    uuid: str
    handle: str | None
    status: str
    site_panel_username: str | None
    referral_count: int
    referred_by: str | None
    streak_count: int
    last_claim_at: datetime | None
    ip_bucket: str | None
    has_fingerprint: bool  # never expose the hash itself — it identifies the browser
    created_at: datetime | None


class DevicePage(BaseModel):
    items: list[DeviceOut]
    total: int
    page: int
    page_size: int


class ClaimOut(BaseModel):
    location: str
    is_change: bool
    created_at: datetime | None


class DevicePeer(BaseModel):
    uuid: str
    handle: str | None
    status: str
    created_at: datetime | None


class DeviceCardOut(DeviceOut):
    claims: int
    recent_claims: list[ClaimOut]
    rewards: list[str]  # one-time grants recorded for this device (pwa / push)
    invited: int  # devices that arrived via this one's link (RAW, uncapped)


def _out(d: SiteDevice) -> DeviceOut:
    return DeviceOut(
        uuid=d.uuid,
        handle=d.handle,
        status=d.status,
        site_panel_username=d.site_panel_username,
        referral_count=d.referral_count,
        referred_by=d.referred_by,
        streak_count=d.streak_count,
        last_claim_at=d.last_claim_at,
        ip_bucket=d.ip_bucket,
        has_fingerprint=bool(d.fingerprint_hash),
        created_at=d.created_at,
    )


@router.get("/", response_model=DevicePage)
async def list_devices(
    request: Request,
    session: DbSession,
    admin: AdminUser,
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=100),
    status: str | None = Query(None),
    search: str | None = Query(None),
    ip_bucket: str | None = Query(None),
) -> DevicePage:
    """A page of devices. ``ip_bucket`` is what the anti-abuse panel deep-links into."""
    if status is not None and status not in _STATUSES:
        raise HTTPException(422, f"status must be one of: {', '.join(sorted(_STATUSES))}")
    repo = SiteDeviceRepository(session)
    rows = await repo.list_page(
        limit=page_size,
        offset=(page - 1) * page_size,
        status=status,
        search=search,
        ip_bucket=ip_bucket,
    )
    return DevicePage(
        items=[_out(d) for d in rows],
        total=await repo.count_filtered(status=status, search=search, ip_bucket=ip_bucket),
        page=page,
        page_size=page_size,
    )


@router.get("/{uuid}", response_model=DeviceCardOut)
async def get_device(
    uuid: str, request: Request, session: DbSession, admin: AdminUser
) -> DeviceCardOut:
    card = await _service(request, session).card(uuid)
    if card is None:
        raise HTTPException(404, "device not found")
    return DeviceCardOut(
        **_out(card.device).model_dump(),
        claims=card.claims,
        recent_claims=[
            ClaimOut(location=c.location, is_change=c.is_change, created_at=c.created_at)
            for c in card.recent_claims
        ],
        rewards=card.rewards,
        invited=card.invited,
    )


@router.get("/{uuid}/peers", response_model=list[DevicePeer])
async def device_peers(
    uuid: str, request: Request, session: DbSession, admin: AdminUser
) -> list[DevicePeer]:
    """Other devices sharing this one's browser fingerprint — the rows behind the anti-abuse count.
    A soft multi-account signal for manual review, never an automatic block."""
    card = await _service(request, session).card(uuid)
    if card is None:
        raise HTTPException(404, "device not found")
    return [
        DevicePeer(uuid=p.uuid, handle=p.handle, status=p.status, created_at=p.created_at)
        for p in card.fingerprint_peers
    ]


@router.post("/{uuid}/block", response_model=DeviceOut)
async def block_device(
    uuid: str, request: Request, session: DbSession, admin: AdminUser
) -> DeviceOut:
    device = await _service(request, session).block(uuid)
    if device is None:
        raise HTTPException(404, "device not found")
    return _out(device)


@router.post("/{uuid}/unblock", response_model=DeviceOut)
async def unblock_device(
    uuid: str, request: Request, session: DbSession, admin: AdminUser
) -> DeviceOut:
    device = await _service(request, session).unblock(uuid)
    if device is None:
        raise HTTPException(404, "device not found")
    return _out(device)


@router.post("/{uuid}/reset", response_model=DeviceOut)
async def reset_device_trial(
    uuid: str, request: Request, session: DbSession, admin: AdminUser
) -> DeviceOut:
    """Free the current trial and clear the cooldown so the device can claim again now. The row,
    its claim history and its rewards are kept — this is forgiveness, not a wipe."""
    device = await _service(request, session).reset_trial(uuid)
    if device is None:
        raise HTTPException(404, "device not found")
    return _out(device)
