"""Site reminder decisions — the device analogue of ``ReminderService`` (no Telegram, push instead).

Maps a Remnawave ``user.expired`` / ``user.limited`` event (or a reconcile probe) for a SITE panel
user back to its ``site_devices`` row and decides the nudge:
- EXPIRED (time up / disabled / gone): self-heal the device to claimable (delete panel account, flip
  to ``available``, clear caches) and nudge "trial ended, claim again".
- LIMITED (data out but time valid): KEEP the account + ``active_config`` so a referral/reward bump
  can revive the SAME config; fire the "volume low, invite" nudge AT MOST ONCE per episode (Redis
  ``SET NX`` guard). Never resets on limited — that would kill the revive path.

Returns a ``SiteNudge`` (device + content keys + render tokens); the caller (webhook / reconcile)
sends the push AFTER committing, best-effort. Decision only — no push I/O, no bot ``users`` row.
"""

from __future__ import annotations

from dataclasses import dataclass

from redis.asyncio import Redis

from gozar.cache.redis import site_limited_notified_key
from gozar.db.models.site_device import SiteDevice, SiteDeviceStatus
from gozar.db.repositories.site_device import SiteDeviceRepository
from gozar.remnawave import RemnawaveClient
from gozar.remnawave.schemas import PanelUser, WebhookUserEvent
from gozar.services.settings_service import SettingsService, SiteSettingKey
from gozar.services.site_trial import reset_device_to_available
from gozar.services.trial import _DEFAULT_TRIAL_HOURS, human_bytes, human_remaining

# VERIFY: Remnawave's event names for the expiry / data-limit transitions (same as the bot handler).
_KIND_FOR_EVENT = {"user.expired": "expired", "user.limited": "limited"}

_EXPIRED_KEYS = ("site_push_expired_title", "site_push_expired_body")
_LIMITED_KEYS = ("site_push_limited_title", "site_push_limited_body")


@dataclass(frozen=True)
class SiteNudge:
    """A push to send to one device: which content copy + the tokens to render it with."""

    device_uuid: str
    title_key: str
    body_key: str
    tokens: dict[str, str]


def nudge_tokens(user: PanelUser) -> dict[str, str]:
    """Push-copy tokens from the panel user record (no extra call). ``{remaining}`` is time LEFT."""
    return {
        "used_traffic": human_bytes(user.traffic.used_bytes),
        "total_traffic": human_bytes(user.traffic_limit_bytes),
        "remaining": human_remaining(user.expire_at),
    }


class SiteReminderService:
    def __init__(
        self,
        device_repo: SiteDeviceRepository,
        settings: SettingsService,
        redis: Redis,
        panel: RemnawaveClient,
    ) -> None:
        self._devices = device_repo
        self._settings = settings
        self._redis = redis
        self._panel = panel

    async def _trial_hours(self) -> int:
        return max(
            await self._settings.get_int(SiteSettingKey.SITE_TRIAL_HOURS, _DEFAULT_TRIAL_HOURS), 1
        )

    async def _limited(self, device: SiteDevice, tokens: dict[str, str]) -> SiteNudge | None:
        # Data out, time valid: keep the account revivable; nudge at most once per episode (SET NX,
        # TTL'd to the trial window). No state change — a reset here kills the bump-revive path.
        first = await self._redis.set(
            site_limited_notified_key(device.uuid),
            "1",
            ex=await self._trial_hours() * 3600,
            nx=True,
        )
        if not first:
            return None
        return SiteNudge(device.uuid, *_LIMITED_KEYS, tokens)

    async def _expired(self, device: SiteDevice, tokens: dict[str, str]) -> SiteNudge | None:
        # Compare-and-swap reset: if a concurrent re-claim already swapped in a fresh trial, the
        # reset is a no-op and we skip the stale "trial ended" nudge.
        if not await reset_device_to_available(self._panel, self._redis, device):
            return None
        return SiteNudge(device.uuid, *_EXPIRED_KEYS, tokens)

    async def apply_event(self, event: WebhookUserEvent) -> SiteNudge | None:
        """Webhook path: route a ``user.expired`` / ``user.limited`` event to its site device."""
        kind = _KIND_FOR_EVENT.get(event.event)
        if kind is None:  # not an expiry/limit event — ignore
            return None
        username = event.data.username
        if not username:
            return None
        device = await self._devices.get_by_site_panel_username(username)
        if device is None or device.status == SiteDeviceStatus.blocked:
            return None
        tokens = nudge_tokens(event.data)
        if kind == "limited":
            return await self._limited(device, tokens)
        return await self._expired(device, tokens)

    async def apply_ended_trial(
        self, device: SiteDevice, tokens: dict[str, str]
    ) -> SiteNudge | None:
        """Reconcile path: a known ``active_config`` device whose trial is TERMINAL (expiry only —
        the reconcile sweep filters out limited-but-time-valid, so the data-limit nudge stays
        webhook-only, mirroring the bot)."""
        if device.status != SiteDeviceStatus.active_config:
            return None
        return await self._expired(device, tokens)
