"""Device identity for the public site — a signed httpOnly cookie, no login, no Telegram.

The cookie is ``<uuid>.<hmac>`` where the HMAC (SHA-256 over the uuid, keyed by
``site_cookie_secret``) is verified in constant time (mirroring the Telegram webhook check). A
first-time visitor is minted a fresh device row + cookie; a returning visitor resolves to their
existing ``site_devices`` row. A light fingerprint hash and a coarse, salted IP bucket are captured
as weak anti-abuse signals (never a hard block; the IP is bucketed + hashed, not stored raw).
"""

from __future__ import annotations

import hashlib
import hmac
import ipaddress
import logging
import uuid as uuid_lib
from typing import Annotated

from fastapi import Depends, HTTPException, Request, Response

from gozar.config.settings import get_settings
from gozar.db.models.site_device import SiteDevice
from gozar.db.repositories.site_device import SiteDeviceRepository
from gozar.web.dependencies import DbSession

logger = logging.getLogger("gozar.web.public")

DEVICE_COOKIE = "gz_device"
# ~13 months — long enough that a device keeps its history across the trial/streak windows.
COOKIE_MAX_AGE = 400 * 24 * 3600


def sign_device(device_uuid: str, secret: str) -> str:
    # Refuse to sign with an empty key: a blank secret makes every HMAC trivially forgeable, so a
    # cookie minted with it is worthless. current_device fails closed before reaching here; this is
    # belt-and-suspenders so an unsigned cookie can never be handed out.
    if not secret:
        raise ValueError("site_cookie_secret is not set — refusing to sign a device cookie")
    mac = hmac.new(secret.encode(), device_uuid.encode(), hashlib.sha256).hexdigest()
    return f"{device_uuid}.{mac}"


def verify_device_cookie(value: str, secret: str) -> str | None:
    """Return the uuid iff the cookie's HMAC matches (constant-time); else None. A blank secret can
    never verify — every forged ``<uuid>.<hmac('')>`` would otherwise validate."""
    if not secret or not value or "." not in value:
        return None
    device_uuid, _, mac = value.partition(".")
    expected = hmac.new(secret.encode(), device_uuid.encode(), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(mac, expected):
        return None
    try:
        uuid_lib.UUID(device_uuid)
    except ValueError:
        return None
    return device_uuid


def client_ip(request: Request) -> str:
    """The caller's IP. uvicorn runs with ``--proxy-headers``, so ``request.client.host`` already
    reflects the real client behind nginx."""
    return request.client.host if request.client else "0.0.0.0"


def _coarse_ip(ip: str) -> str:
    """Coarsen to a /24 (IPv4) or /48 (IPv6) network so we group, not track, exact addresses."""
    try:
        addr = ipaddress.ip_address(ip)
    except ValueError:
        return "unknown"
    prefix = 24 if addr.version == 4 else 48
    return str(ipaddress.ip_network(f"{ip}/{prefix}", strict=False).network_address)


def ip_bucket(request: Request, secret: str) -> str:
    """A salted hash of the coarse IP network — a stable grouping key that never stores a raw IP."""
    coarse = _coarse_ip(client_ip(request))
    return hashlib.sha256(f"{secret}:{coarse}".encode()).hexdigest()[:64]


def fingerprint_hash(request: Request) -> str:
    """A light device fingerprint (user-agent + accept-language) — a weak signal, never an id."""
    ua = request.headers.get("user-agent", "")
    al = request.headers.get("accept-language", "")
    return hashlib.sha256(f"{ua}|{al}".encode()).hexdigest()[:64]


async def _referrer(
    request: Request, repo: SiteDeviceRepository, new_uuid: str
) -> str | None:
    """The inviter's device UUID from a ``?ref=`` link, captured once when a device is minted.

    ``ref`` may be either the inviter's public handle (``GZ-…`` — the form invite links now use) or
    a raw device uuid (legacy links). A handle is resolved to its device UUID; a well-formed uuid is
    taken as-is (no existence check — a non-existent referrer simply earns no credit later). We
    always STORE the uuid so ``referred_by`` stays a stable foreign key into ``site_devices``."""
    ref = request.query_params.get("ref", "").strip()
    if not ref or ref == new_uuid:
        return None
    try:
        uuid_lib.UUID(ref)
        return ref  # legacy uuid ref link
    except ValueError:
        pass
    inviter = await repo.get_by_handle(ref)  # a handle (GZ-…) → its device uuid
    if inviter is None or inviter.uuid == new_uuid:
        return None
    return inviter.uuid


def set_device_cookie(response: Response, request: Request, device_uuid: str) -> None:
    """Write the signed device cookie onto ``response`` — shared by the first-visit mint and the
    transfer-redeem identity switch (P6), so both set identical flags. ``Secure`` follows the
    request scheme (https behind nginx via ``--proxy-headers``; http in local dev/tests) so the
    cookie round-trips in every environment."""
    secret = get_settings().site_cookie_secret.get_secret_value()
    response.set_cookie(
        DEVICE_COOKIE,
        sign_device(device_uuid, secret),
        max_age=COOKIE_MAX_AGE,
        httponly=True,
        secure=request.url.scheme == "https",
        samesite="lax",
        path="/",
    )


def clear_device_cookie(response: Response) -> None:
    """Delete the device cookie (P6 device reset). The cookie is httpOnly, so only the server can
    clear it; the browser then mints a fresh identity on its next request."""
    response.delete_cookie(DEVICE_COOKIE, path="/")


async def current_device(request: Request, response: Response, session: DbSession) -> SiteDevice:
    """Resolve (or mint) the caller's ``site_devices`` row from the signed cookie.

    Returns the existing device for a valid cookie; otherwise mints a new uuid + device row and sets
    the signed cookie on the response.
    """
    settings = get_settings()
    secret = settings.site_cookie_secret.get_secret_value()
    if not secret:
        # Fail closed: with no signing key, every device identity is forgeable (anyone could become
        # any device — read /status, claim, mint a transfer). Refuse to serve rather than hand out
        # spoofable cookies. The installer always generates one; only a hand-rolled setup hits this.
        logger.error("site_cookie_secret is not set — refusing to mint device identities")
        raise HTTPException(status_code=503, detail="site_not_configured")
    repo = SiteDeviceRepository(session)

    device_uuid = verify_device_cookie(request.cookies.get(DEVICE_COOKIE, ""), secret)
    if device_uuid is not None:
        device = await repo.get(device_uuid)
        if device is not None:
            return device

    new_uuid = str(uuid_lib.uuid4())
    device, _ = await repo.get_or_create(
        new_uuid,
        fingerprint_hash=fingerprint_hash(request),
        ip_bucket=ip_bucket(request, secret),
        referred_by=await _referrer(request, repo, new_uuid),
    )
    set_device_cookie(response, request, new_uuid)
    return device


CurrentDevice = Annotated[SiteDevice, Depends(current_device)]
