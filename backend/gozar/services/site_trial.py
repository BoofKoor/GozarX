"""Site trial service — the website's 'one free daily config' flow (device-keyed, site_* economy).

The parallel of ``TrialService`` for site devices: it REUSES the panel client + the pure helpers in
``services.trial`` (cooldown / human formatters / the terminal-state check) but operates on a
``SiteDevice`` (never the bot ``users`` table), keys its cache by device uuid, reads the ``site_*``
settings, and writes ``site_claims``. It preserves the two hard invariants:

* **Location matched by remark NAME**, never a list index (the v1 ``links[index]`` bug).
* **The DB status flip is the LAST step** — ``status`` + ``site_panel_username`` are written only
  after the panel create AND the subscription read both succeed with >=1 usable link, so a partial
  failure leaves the device ``available`` (its orphaned panel account expires / self-heals).

Site panel usernames are ``s{device8}_{ts}`` — a distinct prefix from the bot's ``g{tid}_{ts}`` — so
the two products' panel accounts never collide.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from redis.asyncio import Redis
from sqlalchemy import update
from sqlalchemy.ext.asyncio import async_object_session

from gozar.cache.redis import site_limited_notified_key, site_sub_cache_key
from gozar.db.models.site_device import SiteDevice, SiteDeviceStatus
from gozar.db.repositories.site_claim import SiteClaimRepository
from gozar.db.repositories.site_reward import SiteRewardRepository
from gozar.remnawave import RemnawaveClient, RemnawaveError
from gozar.remnawave.schemas import Subscription
from gozar.services.settings_service import SettingsService, SiteSettingKey
from gozar.services.site_economy import (
    next_streak_count,
    site_compute_traffic_bytes,
    site_device_allowance_bytes,
    streak_is_active,
)
from gozar.services.trial import (
    AlreadyClaimedToday,
    NoLocations,
    NotReady,
    PanelError,
    TrialService,
    cooldown_remaining,
    human_bytes,
    human_remaining,
    in_cooldown,
)

logger = logging.getLogger("gozar.services.site_trial")

_DEFAULT_SITE_TRIAL_HOURS = 24


@dataclass(frozen=True)
class Delivered:
    """A config for a chosen location was delivered. ``changed`` is True when an already-active
    device just switched location (no new provision / no new cooldown)."""

    location: str
    link: str
    expires: str  # human time-remaining ("19h 54m")
    size: str  # daily allowance, human ("1.5 GB")
    changed: bool = False


# Reuses the bot's storage-agnostic result variants for the shared states.
SiteClaimResult = Delivered | AlreadyClaimedToday | NotReady | NoLocations | PanelError


@dataclass(frozen=True)
class SiteStatusInfo:
    """The 'my status' view. ``live`` is False when the panel was unreachable — the device-level
    fields (allowance, invites, history, cooldown) are still valid, only the live traffic isn't."""

    status: str
    active: bool
    has_config: bool
    live: bool
    data_exhausted: bool
    daily_limit: str
    daily_limit_bytes: int
    usage: str
    usage_bytes: int
    remaining: str  # time left on the current config
    cooldown: str  # time until the next fresh claim ("" when already elapsed)
    can_claim: bool
    configs: int  # claim-history count
    referral_count: int
    referral_cap: int
    streak_count: int
    streak_days: int
    streak_active: bool  # streak_count has reached streak_days (the bonus is standing)
    trial_hours: int  # rolling window each config lasts / renews on (the "renews every Nh" copy)
    location: str | None  # current config's location NAME
    link: str | None  # current config's link


@dataclass(frozen=True)
class _Cached:
    links: dict[str, str]
    expires: str | None


async def bump_live_trial(
    panel: RemnawaveClient, redis: Redis, device: SiteDevice, new_daily_bytes: int
) -> None:
    """Raise a device's live-trial panel limit to a new allowance — also the LIMITED->ACTIVE revive
    path (PATCHing a higher limit re-activates a data-exhausted account). Best-effort: a single
    bounded call, logged and ignored on failure; drops the nudge guard + cached sub on success.
    Shared by the referral credit and the reward claim (both raise the same device's allowance)."""
    if device.status != SiteDeviceStatus.active_config or not device.site_panel_username:
        return
    try:
        panel_user = await panel.get_user(device.site_panel_username)
        if panel_user and panel_user.uuid:
            await panel.update_traffic_limit(panel_user.uuid, new_daily_bytes)
            await redis.delete(site_limited_notified_key(device.uuid))
            await redis.delete(site_sub_cache_key(device.uuid))
    except RemnawaveError:
        logger.warning("site live-bump failed for device %s", device.uuid)


async def reset_device_to_available(
    panel: RemnawaveClient, redis: Redis, device: SiteDevice
) -> bool:
    """Self-heal a device with an ENDED trial back to claimable: free the panel account
    (best-effort, single bounded call), flip the row to ``available`` + drop its panel username, and
    clear its cached sub + data-limit nudge guard. Shared by the lazy self-heal (SiteTrialService)
    and the proactive teardown on an expiry webhook / reconcile sweep (SiteReminderService).

    The row flip is a compare-and-swap on the panel username, NOT a blind write: a concurrent
    re-claim (which swaps in a fresh panel account in another session) makes the guarded UPDATE
    match zero rows, so we never clobber the new trial back to available. Returns True iff this call
    performed the reset — the caller skips the now-stale expiry nudge when it returns False.
    """
    username = device.site_panel_username
    if username:
        try:
            await panel.delete_user_by_username(username)
        except RemnawaveError:
            logger.warning("site self-heal: panel delete failed for %s", device.uuid)
    session = async_object_session(device)
    guard = (
        SiteDevice.site_panel_username.is_(None)
        if username is None
        else SiteDevice.site_panel_username == username
    )
    result = await session.execute(
        update(SiteDevice)
        .where(SiteDevice.uuid == device.uuid, guard)
        .values(status=SiteDeviceStatus.available, site_panel_username=None)
        .execution_options(synchronize_session=False)
    )
    did_reset = bool(result.rowcount)
    if did_reset:
        # We hold the row lock until commit, so syncing the in-memory read-model (a redundant,
        # same-value ORM write on flush) cannot be clobbered by a concurrent claim.
        device.status = SiteDeviceStatus.available
        device.site_panel_username = None
    await redis.delete(site_sub_cache_key(device.uuid))
    await redis.delete(site_limited_notified_key(device.uuid))
    return did_reset


class SiteTrialService:
    def __init__(
        self,
        panel: RemnawaveClient,
        settings: SettingsService,
        site_claim_repo: SiteClaimRepository,
        site_reward_repo: SiteRewardRepository,
        redis: Redis,
    ) -> None:
        self._panel = panel
        self._settings = settings
        self._claims = site_claim_repo
        self._rewards = site_reward_repo
        self._redis = redis

    # --- settings / cache -----------------------------------------------------------------------
    async def _hours(self) -> int:
        return max(
            await self._settings.get_int(
                SiteSettingKey.SITE_TRIAL_HOURS, _DEFAULT_SITE_TRIAL_HOURS
            ),
            1,
        )

    async def _store_cache(self, uuid: str, links: dict[str, str], expires: str | None) -> None:
        payload = json.dumps({"links": links, "expires": expires})
        await self._redis.set(site_sub_cache_key(uuid), payload, ex=await self._hours() * 3600)

    async def _load_cache(self, uuid: str) -> _Cached | None:
        raw = await self._redis.get(site_sub_cache_key(uuid))
        if not raw:
            return None
        try:
            data = json.loads(raw)
        except (ValueError, TypeError):
            return None
        links = data.get("links") if isinstance(data, dict) else None
        if not isinstance(links, dict):
            return None
        return _Cached({str(k): str(v) for k, v in links.items()}, data.get("expires"))

    async def _clear_cache(self, uuid: str) -> None:
        await self._redis.delete(site_sub_cache_key(uuid))

    async def _filter_locations(self, links: dict[str, str]) -> dict[str, str]:
        """Intersect the link map with the SITE_LOCATIONS allowlist (empty -> keep all)."""
        allow = await self._settings.get_list(SiteSettingKey.SITE_LOCATIONS)
        if not allow:
            return dict(links)
        allowed = set(allow)
        return {name: link for name, link in links.items() if name in allowed}

    # --- self-heal ------------------------------------------------------------------------------
    async def _reset(self, device: SiteDevice) -> None:
        await reset_device_to_available(self._panel, self._redis, device)

    async def _refresh_active(
        self, device: SiteDevice
    ) -> tuple[Subscription, dict[str, str]] | None:
        """Re-read an active device's live state; self-heal an ended/missing trial to available.

        Reuses ``TrialService._is_expired`` (a pure, storage-agnostic terminal test). A transient
        (non-404) ``RemnawaveError`` is re-raised so the caller maps it to ``PanelError``."""
        username = device.site_panel_username
        if not username:
            await self._reset(device)
            return None
        try:
            sub, links = await self._panel.subscription(username)
        except RemnawaveError as exc:
            if exc.status_code == 404:
                await self._reset(device)
                return None
            raise
        if TrialService._is_expired(sub):
            await self._reset(device)
            return None
        filtered = await self._filter_locations(links)
        await self._store_cache(device.uuid, filtered, sub.user.expires_at)
        return sub, filtered

    # --- delivery -------------------------------------------------------------------------------
    def _username(self, device: SiteDevice) -> str:
        return f"s{device.uuid[:8]}_{int(datetime.now(UTC).timestamp())}"

    @staticmethod
    def _pick(links: dict[str, str], location_name: str) -> tuple[str, str]:
        """The (name, link) for the requested location, matched by NAME; falls back to the first
        available if the exact name isn't in the squad-derived map. Caller guarantees non-empty."""
        if location_name in links:
            return location_name, links[location_name]
        return next(iter(links.items()))

    async def _allowance_bytes(self, device: SiteDevice) -> int:
        return await site_device_allowance_bytes(self._settings, device, self._rewards)

    async def _allowance_size(self, device: SiteDevice) -> str:
        return human_bytes(await self._allowance_bytes(device))

    async def _deliver(
        self,
        device: SiteDevice,
        links: dict[str, str],
        expires: str | None,
        location_name: str,
        *,
        changed: bool,
    ) -> Delivered:
        name, link = self._pick(links, location_name)
        await self._claims.add(device.uuid, name)  # one row per delivery (location = remark NAME)
        return Delivered(
            location=name,
            link=link,
            expires=human_remaining(expires),
            size=await self._allowance_size(device),
            changed=changed,
        )

    # --- public flow ----------------------------------------------------------------------------
    async def available_locations(self, device: SiteDevice) -> list[str] | PanelError:
        """Location names for the picker. For an active device: the cached (or live) subscription
        map; for a fresh device: the SITE_LOCATIONS setting (the upfront picker options)."""
        cached = await self._load_cache(device.uuid)
        if cached is not None:
            return list(cached.links.keys())
        if device.status == SiteDeviceStatus.active_config:
            try:
                refreshed = await self._refresh_active(device)
            except RemnawaveError:
                return PanelError()
            if refreshed is not None:
                _, links = refreshed
                return list(links.keys())
        return await self._settings.get_list(SiteSettingKey.SITE_LOCATIONS)

    async def claim(self, device: SiteDevice, location_name: str) -> SiteClaimResult:
        # 1. Already holding a live config? Re-read (self-heals an ended trial). If still valid,
        #    this is a change-location: deliver the chosen link from the account (no new provision).
        if device.status == SiteDeviceStatus.active_config:
            try:
                refreshed = await self._refresh_active(device)
            except RemnawaveError:
                return PanelError()
            if refreshed is not None:
                sub, links = refreshed
                if not links:
                    return NoLocations()
                return await self._deliver(
                    device, links, sub.user.expires_at, location_name, changed=True
                )
            # else: reset to available — fall through to a fresh claim.

        # 2. One claim per rolling site_trial_hours window (anchored on the last PROVISION time).
        hours = await self._hours()
        if in_cooldown(device.last_claim_at, hours):
            return AlreadyClaimedToday(cooldown_remaining(device.last_claim_at, hours))

        # 3. Site trial squad configured (admin 'website' wizard done)?
        squad = await self._settings.get(SiteSettingKey.SITE_TRIAL_SQUAD)
        if not squad:
            return NotReady()

        # 4. Panel call 1 — create a fresh trial account. Device stays available on failure.
        claim_at = datetime.now(UTC)
        # A fresh claim advances the consecutive-daily-claim streak. Compute the streak this claim
        # WOULD produce and fold its bonus into the provisioned allowance up front, but only persist
        # it (step 6) once the claim actually succeeds — a failed claim must never move the streak.
        new_streak = next_streak_count(device.streak_count, device.last_claim_at, claim_at, hours)
        streak_days = await self._settings.get_int(SiteSettingKey.SITE_STREAK_DAYS, 0)
        claimed_rewards = await self._rewards.types_for_device(device.uuid)
        traffic = await site_compute_traffic_bytes(
            self._settings,
            device.referral_count,
            rewards=claimed_rewards,
            streak_active=streak_days > 0 and new_streak >= streak_days,
        )
        expire_at = claim_at + timedelta(hours=hours)
        username = self._username(device)
        try:
            await self._panel.create_trial_user(username, traffic, expire_at, [squad])
        except RemnawaveError:
            return PanelError()

        # 5. Panel call 2 — read THAT account's subscription (the single source for picker + links).
        try:
            sub, links = await self._panel.subscription(username)
        except RemnawaveError:
            return PanelError()
        filtered = await self._filter_locations(links)
        if not filtered:
            return NoLocations()  # device left available; the orphaned panel account expires.

        # 6. Only now (create + >=1 link both OK) cache + flip DB status LAST.
        expires = sub.user.expires_at or expire_at.isoformat()
        await self._store_cache(device.uuid, filtered, expires)
        await self._redis.delete(site_limited_notified_key(device.uuid))
        device.status = SiteDeviceStatus.active_config
        device.site_panel_username = username
        device.last_claim_at = claim_at  # cooldown starts at provision, aligned with panel expiry
        device.streak_count = new_streak  # consecutive-claim streak advanced on a real provision
        device.last_streak_at = claim_at
        return await self._deliver(device, filtered, expires, location_name, changed=False)

    async def status(self, device: SiteDevice) -> SiteStatusInfo:
        """The full 'my status' view. Reads live panel traffic for an active device (self-healing an
        ended trial); degrades to ``live=False`` (never an error) when the panel is unreachable, so
        the device-level fields (allowance, invites, history, cooldown) always render."""
        active = device.status == SiteDeviceStatus.active_config
        live, exhausted, usage_bytes = True, False, 0
        usage, remaining = "—", "—"  # unknown until live traffic is read
        location: str | None = None
        link: str | None = None
        if active:
            try:
                refreshed = await self._refresh_active(device)
            except RemnawaveError:
                live = False  # transient — keep the device active, just no live traffic
            else:
                if refreshed is None:
                    active = False  # self-healed to available
                else:
                    sub, links = refreshed
                    usage_bytes = sub.user.traffic_used_bytes
                    usage = human_bytes(usage_bytes)
                    remaining = human_remaining(sub.user.expires_at)
                    exhausted = TrialService._is_data_exhausted(sub)
                    loc = await self._claims.latest_location_for_device(device.uuid)
                    if loc and loc in links:
                        location, link = loc, links[loc]
                    elif links:
                        location, link = next(iter(links.items()))

        daily_bytes = await self._allowance_bytes(device)
        hours = await self._hours()
        cooling = in_cooldown(device.last_claim_at, hours)
        streak_days = await self._settings.get_int(SiteSettingKey.SITE_STREAK_DAYS, 0)
        return SiteStatusInfo(
            status=device.status,
            active=active,
            has_config=active,
            live=live,
            data_exhausted=exhausted,
            daily_limit=human_bytes(daily_bytes),
            daily_limit_bytes=daily_bytes,
            usage=usage,
            usage_bytes=usage_bytes,
            remaining=remaining,
            cooldown=cooldown_remaining(device.last_claim_at, hours) if cooling else "",
            can_claim=not cooling,
            configs=await self._claims.count_for_device(device.uuid),
            referral_count=device.referral_count,
            referral_cap=await self._settings.get_int(SiteSettingKey.SITE_REFERRAL_REWARD_LIMIT, 0),
            streak_count=device.streak_count,
            streak_days=streak_days,
            streak_active=streak_is_active(device, streak_days),
            trial_hours=hours,
            location=location,
            link=link,
        )
