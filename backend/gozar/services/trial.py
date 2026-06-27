"""Trial service — the core 'one free daily config' flow (provision, claim, status, locations).

**Single source of truth for locations.** A claim creates a fresh 24h panel user, reads THAT user's
own subscription, and both the picker names AND the link handed back on a pick come from that one
(cached) response — never a cross-index between two separate lists (the v1 ``links[index]`` bug).
Change-location reuses the same cache; it never creates a second panel user.

**The DB status flip is the LAST step of a claim.** ``status -> active_config`` + ``panel_username``
are written only after BOTH the create and the subscription read succeed with >=1 usable link. A
partial failure leaves the user ``available`` (an orphaned panel user is harmless — its 24h expiry
cleans it up), so we never half-commit a user into a stuck state.

**Lazy self-heal.** Between a Phase-4 claim and the Phase-5 expiry webhook, an ``active_config``
user whose trial has already ended would otherwise be stuck on "already active" forever. Whenever we
touch such a user we re-read the live panel state we need anyway; if it reads expired / limited /
missing we reset them to ``available`` so they can claim again.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from redis.asyncio import Redis

from gozar.cache.redis import sub_cache_key
from gozar.db.models.enums import UserStatus
from gozar.db.models.user import User
from gozar.db.repositories.config_log import ConfigLogRepository
from gozar.remnawave import RemnawaveClient, RemnawaveError
from gozar.remnawave.schemas import Subscription
from gozar.services.settings_service import SettingKey, SettingsService

logger = logging.getLogger("gozar.services.trial")

# Fallbacks used ONLY if the (always-seeded) setting is missing — not a place to encode economics.
_DEFAULT_DAILY_MB = 1024
_DEFAULT_TRIAL_HOURS = 24
# Panel statuses that mean "this trial has ended" (used by the self-heal check).
_ENDED_STATUSES = {"EXPIRED", "LIMITED", "DISABLED"}


# --- claim() result variants -------------------------------------------------------------------
@dataclass(frozen=True)
class Provisioned:
    """A fresh trial was created; show the size + the location picker."""

    remarks: list[str]
    size: str


@dataclass(frozen=True)
class AlreadyActive:
    """The user already holds a live trial; offer the picker as a change-location."""

    remarks: list[str]


@dataclass(frozen=True)
class AlreadyClaimedToday:
    """One claim per UTC calendar day already used."""


@dataclass(frozen=True)
class NotReady:
    """No trial squad configured yet (first-run wizard not completed)."""


@dataclass(frozen=True)
class NoLocations:
    """The subscription carried no usable links (or the allowlist intersects to empty)."""


@dataclass(frozen=True)
class PanelError:
    """A bounded panel call failed transiently; the user's state is unchanged."""


ClaimResult = (
    Provisioned | AlreadyActive | AlreadyClaimedToday | NotReady | NoLocations | PanelError
)


@dataclass(frozen=True)
class StatusInfo:
    """Rendered tokens for the status screen (``active`` controls the change-location button)."""

    tg_id: int
    referrals: int
    daily_limit: str
    configs: int
    usage: str
    remaining: str
    active: bool


@dataclass(frozen=True)
class Delivery:
    """A single delivered config: the location name, its link, and a human expiry."""

    location: str
    link: str
    expires: str


@dataclass(frozen=True)
class _Cached:
    """The cached subscription map backing the picker + link lookups for one user."""

    links: dict[str, str]
    expires: str | None


def start_of_today_utc() -> datetime:
    """Midnight UTC today — the boundary for the one-claim-per-calendar-day guard."""
    now = datetime.now(UTC)
    return now.replace(hour=0, minute=0, second=0, microsecond=0)


def _gen_username(telegram_id: int) -> str:
    """A unique panel username per claim (each claim is a brand-new 24h user)."""
    return f"g{telegram_id}_{int(datetime.now(UTC).timestamp())}"


def _parse_dt(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)


def human_bytes(num: int) -> str:
    value = float(max(num, 0))
    for unit in ("B", "KB", "MB", "GB"):
        if value < 1024:
            return f"{value:.0f} {unit}" if unit == "B" else f"{value:.1f} {unit}"
        value /= 1024
    return f"{value:.1f} TB"


def _human_duration(delta: timedelta) -> str:
    total = int(delta.total_seconds())
    if total <= 0:
        return "0m"
    hours, rem = divmod(total, 3600)
    minutes = rem // 60
    if hours and minutes:
        return f"{hours}h {minutes}m"
    return f"{hours}h" if hours else f"{minutes}m"


def _format_expires(value: str | None) -> str:
    parsed = _parse_dt(value)
    return parsed.strftime("%Y-%m-%d %H:%M UTC") if parsed else "—"


async def compute_traffic_bytes(settings: SettingsService, referral_count: int) -> int:
    """Daily allowance + the configured (capped) referral bonus, in bytes.

    The single source of the trial quota math — reused by the trial claim, the referral live-bump,
    and the invite screen. Never hardcodes the reward/cap (they come from settings).
    """
    daily_mb = await settings.get_int(SettingKey.DAILY_LIMIT_MB, _DEFAULT_DAILY_MB)
    reward_mb = await settings.get_int(SettingKey.REFERRAL_REWARD_MB, 0)
    cap = await settings.get_int(SettingKey.REFERRAL_REWARD_LIMIT, 0)
    rewarded = min(referral_count, cap)
    return (daily_mb + rewarded * reward_mb) * 1024 * 1024


class TrialService:
    def __init__(
        self,
        panel: RemnawaveClient,
        settings: SettingsService,
        config_log_repo: ConfigLogRepository,
        redis: Redis,
    ) -> None:
        self._panel = panel
        self._settings = settings
        self._config_log_repo = config_log_repo
        self._redis = redis

    # --- cache helpers (the quota math lives in module-level compute_traffic_bytes) --------------
    async def _store_cache(
        self, telegram_id: int, links: dict[str, str], expires: str | None
    ) -> None:
        hours = max(await self._settings.get_int(SettingKey.TRIAL_HOURS, _DEFAULT_TRIAL_HOURS), 1)
        payload = json.dumps({"links": links, "expires": expires})
        await self._redis.set(sub_cache_key(telegram_id), payload, ex=hours * 3600)

    async def _load_cache(self, telegram_id: int) -> _Cached | None:
        raw = await self._redis.get(sub_cache_key(telegram_id))
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

    async def _clear_cache(self, telegram_id: int) -> None:
        await self._redis.delete(sub_cache_key(telegram_id))

    async def _filter_locations(self, links: dict[str, str]) -> dict[str, str]:
        """Intersect the link map with the LOCATIONS allowlist (empty allowlist -> keep all)."""
        allow = await self._settings.get_list(SettingKey.LOCATIONS)
        if not allow:
            return dict(links)
        allowed = set(allow)
        return {name: link for name, link in links.items() if name in allowed}

    # --- self-heal ------------------------------------------------------------------------------
    @staticmethod
    def _is_expired(sub: Subscription) -> bool:
        if not sub.is_found:
            return True
        if sub.user.user_status.upper() in _ENDED_STATUSES:
            return True
        expires = _parse_dt(sub.user.expires_at)
        return expires is not None and expires <= datetime.now(UTC)

    async def _reset(self, user: User) -> None:
        user.status = UserStatus.available
        user.panel_username = None
        await self._clear_cache(user.telegram_id)

    async def _refresh_active(self, user: User) -> tuple[Subscription, dict[str, str]] | None:
        """Re-read an active_config user's live state.

        Returns ``(sub, filtered_links)`` while the trial is still valid, or ``None`` after
        self-healing an ended/missing trial back to ``available``. A transient ``RemnawaveError``
        (non-404) is re-raised so the caller can map it to ``PanelError`` without touching state.
        """
        username = user.panel_username
        if not username:
            await self._reset(user)
            return None
        try:
            sub, links = await self._panel.subscription(username)
        except RemnawaveError as exc:
            if exc.status_code == 404:
                await self._reset(user)
                return None
            raise
        if self._is_expired(sub):
            await self._reset(user)
            return None
        filtered = await self._filter_locations(links)
        await self._store_cache(user.telegram_id, filtered, sub.user.expires_at)
        return sub, filtered

    # --- public flow ----------------------------------------------------------------------------
    async def claim(self, user: User) -> ClaimResult:
        # 1. Already holding a config? Re-read live state (self-heals an ended trial to available).
        if user.status is UserStatus.active_config:
            try:
                refreshed = await self._refresh_active(user)
            except RemnawaveError:
                return PanelError()
            if refreshed is not None:
                _, links = refreshed
                return AlreadyActive(list(links.keys()))
            # else: reset to available — fall through to a fresh claim.

        # 2. One claim per UTC calendar day.
        if await self._config_log_repo.count_for_user_since(user.telegram_id, start_of_today_utc()):
            return AlreadyClaimedToday()

        # 3. Trial squad configured (first-run wizard done)?
        squad = await self._settings.get(SettingKey.TRIAL_SQUAD)
        if not squad:
            return NotReady()

        # 4. Panel call 1 — create a fresh 24h trial user. User stays `available` on failure.
        traffic_bytes = await compute_traffic_bytes(self._settings, user.referral_count)
        hours = max(await self._settings.get_int(SettingKey.TRIAL_HOURS, _DEFAULT_TRIAL_HOURS), 1)
        expire_at = datetime.now(UTC) + timedelta(hours=hours)
        username = _gen_username(user.telegram_id)
        try:
            await self._panel.create_trial_user(username, traffic_bytes, expire_at, [squad])
        except RemnawaveError:
            return PanelError()

        # 5. Panel call 2 — read THAT user's subscription: the single source for picker + links.
        try:
            sub, links = await self._panel.subscription(username)
        except RemnawaveError:
            return PanelError()
        filtered = await self._filter_locations(links)
        if not filtered:
            return NoLocations()  # leaves the user `available`; the orphaned panel user expires.

        # 6. Only now (create + >=1 link both OK) cache the map and flip the DB status LAST.
        expires = sub.user.expires_at or expire_at.isoformat()
        await self._store_cache(user.telegram_id, filtered, expires)
        user.status = UserStatus.active_config
        user.panel_username = username
        return Provisioned(list(filtered.keys()), human_bytes(traffic_bytes))

    async def status(self, user: User) -> StatusInfo | PanelError:
        usage, remaining, active = "—", "—", False
        if user.status is UserStatus.active_config:
            try:
                refreshed = await self._refresh_active(user)
            except RemnawaveError:
                return PanelError()
            if refreshed is not None:
                sub, _ = refreshed
                usage = human_bytes(sub.user.traffic_used_bytes)
                expires = _parse_dt(sub.user.expires_at)
                remaining = _human_duration(expires - datetime.now(UTC)) if expires else "—"
                active = True
        daily_limit = human_bytes(await compute_traffic_bytes(self._settings, user.referral_count))
        return StatusInfo(
            tg_id=user.telegram_id,
            referrals=user.referral_count,
            daily_limit=daily_limit,
            configs=await self._config_log_repo.count_for_user(user.telegram_id),
            usage=usage,
            remaining=remaining,
            active=active,
        )

    async def locations(self, user: User) -> list[str] | PanelError:
        """Location names for the change-location picker (cache first, else a live refresh)."""
        cached = await self._load_cache(user.telegram_id)
        if cached is not None:
            return list(cached.links.keys())
        if user.status is UserStatus.active_config:
            try:
                refreshed = await self._refresh_active(user)
            except RemnawaveError:
                return PanelError()
            if refreshed is not None:
                _, links = refreshed
                return list(links.keys())
        return []

    async def link_for(self, user: User, index: int) -> Delivery | None:
        """The (location, link, expiry) at ``index`` in the cached picker — matched by NAME."""
        cached = await self._load_cache(user.telegram_id)
        if cached is None and user.status is UserStatus.active_config:
            try:
                refreshed = await self._refresh_active(user)
            except RemnawaveError:
                return None
            if refreshed is not None:
                sub, links = refreshed
                cached = _Cached(links, sub.user.expires_at)
        if cached is None:
            return None
        names = list(cached.links.keys())
        if index < 0 or index >= len(names):
            return None
        name = names[index]
        return Delivery(name, cached.links[name], _format_expires(cached.expires))
