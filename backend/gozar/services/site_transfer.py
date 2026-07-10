"""Device-transfer service — account-less cross-device continuity via a one-time code.

The source device mints a short code (Redis ``SET nx ex`` — a 10-minute expiry); a new browser
redeems it (``GETDEL`` — single use) to ADOPT the source device's identity (the route then re-points
the browser's signed cookie to the source uuid, so it simply *becomes* that device). No account, no
Telegram: the code is the only bridge. Every Redis op is a single bounded call — never a retry loop.
The code lives only in Redis (no table, no migration); ``site_messages`` is the site's only new
persistent P6 surface.
"""

from __future__ import annotations

import logging
import re
import secrets
from dataclasses import dataclass

from redis.asyncio import Redis

from gozar.cache.redis import site_transfer_key
from gozar.db.models.site_device import SiteDevice, SiteDeviceStatus
from gozar.db.repositories.site_device import SiteDeviceRepository

logger = logging.getLogger("gozar.web.public")

# Unambiguous uppercase alphabet (no 0/O/1/I/L) — the code is shown LTR monospace for hand-typing.
_ALPHABET = "23456789ABCDEFGHJKMNPQRSTUVWXYZ"
_CODE_LEN = 8
_TTL_SECONDS = 600  # 10 minutes, per the design; mirrors site_transfer_key's contract.
_MINT_ATTEMPTS = 5  # bounded regen if a fresh code collides with a live one (vanishingly unlikely).


@dataclass(frozen=True)
class TransferCode:
    code: str
    expires_in: int


@dataclass(frozen=True)
class RedeemResult:
    """The source device a redeemed code points at — the route re-points the caller's cookie here.
    Carries a tiny summary so the 'identity restored' state has something to show immediately."""

    device_uuid: str
    has_config: bool
    referral_count: int


class SiteTransferService:
    def __init__(self, device_repo: SiteDeviceRepository, redis: Redis) -> None:
        self._devices = device_repo
        self._redis = redis

    def _new_code(self) -> str:
        return "".join(secrets.choice(_ALPHABET) for _ in range(_CODE_LEN))

    async def create_code(self, device: SiteDevice) -> TransferCode | None:
        """Mint a one-time transfer code pointing at ``device``. ``SET nx`` never overwrites a live
        code; a collision (astronomically unlikely) is retried a bounded number of times. Returns
        None only if every bounded attempt collided — the route surfaces a 'try again'."""
        for _ in range(_MINT_ATTEMPTS):
            code = self._new_code()
            stored = await self._redis.set(
                site_transfer_key(code), device.uuid, ex=_TTL_SECONDS, nx=True
            )
            if stored:
                return TransferCode(code=code, expires_in=_TTL_SECONDS)
        logger.warning("transfer code mint exhausted attempts for device %s", device.uuid)
        return None

    async def redeem(self, code: str) -> RedeemResult | None:
        """Consume a transfer code (``GETDEL`` — single use) and return the SOURCE device summary,
        or None if the code is unknown/expired or its device has since vanished. Wrong and expired
        are indistinguishable server-side (both leave no key), so both map to None → 'invalid'.

        Input is normalized case-insensitively and stripped of any non-alphanumerics, so the
        display form ``XXXX-XXXX`` (the hyphen is display-only) and stray spaces both redeem."""
        normalized = re.sub(r"[^A-Z0-9]", "", code.upper())
        if not normalized:
            return None
        source_uuid = await self._redis.getdel(site_transfer_key(normalized))
        if not source_uuid:
            return None
        device = await self._devices.get(source_uuid)
        if device is None:
            return None
        return RedeemResult(
            device_uuid=device.uuid,
            has_config=device.status == SiteDeviceStatus.active_config,
            referral_count=device.referral_count,
        )
