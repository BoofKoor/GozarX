"""Trial service — the core 'one free daily config' flow (provision, claim, status, locations).

**Single source of truth for locations.** A claim creates a fresh 24h panel user, reads THAT user's
own subscription, and both the picker names AND the link handed back on a pick come from that one
(cached) response — never a cross-index between two separate lists (the v1 ``links[index]`` bug).
Change-location reuses the same cache; it never creates a second panel user.

**The DB status flip is the LAST step of a claim.** ``status -> active_config`` + ``panel_username``
are written only after BOTH the create and the subscription read succeed with >=1 usable link. A
partial failure leaves the user ``available``; the orphaned panel user from a partial create is
cleaned up by the next reset/self-heal (Remnawave only DISABLES an expired user, it never deletes
one), so we never half-commit a user into a stuck state.

**Lazy self-heal.** Between a Phase-4 claim and the Phase-5 expiry webhook, an ``active_config``
user whose trial has already ended would otherwise be stuck on "already active" forever. Whenever we
touch such a user we re-read the live panel state we need anyway; if the trial is TERMINAL (time
expired / disabled / missing) we reset them to ``available`` (deleting the dead panel account) so
they can claim again.

**Data-limit ≠ time-expiry.** A trial that ran out of DATA (panel ``LIMITED``) but whose time is
still valid is NOT terminal: we keep the account and ``active_config`` so a referral traffic bump
can revive the SAME config. Only TIME expiry deletes the panel account. The status/config screens
surface this via ``data_exhausted`` ("invite to revive"); the data-limit nudge is webhook-only.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from redis.asyncio import Redis

from gozar.cache.redis import limited_notified_key, sub_cache_key
from gozar.db.models.enums import UserStatus
from gozar.db.models.user import User
from gozar.db.repositories.config_log import ConfigLogRepository
from gozar.remnawave import RemnawaveClient, RemnawaveError
from gozar.remnawave.schemas import PanelUser, Subscription
from gozar.services.settings_service import SettingKey, SettingsService

logger = logging.getLogger("gozar.services.trial")

# Fallbacks used ONLY if the (always-seeded) setting is missing — not a place to encode economics.
_DEFAULT_DAILY_MB = 1024
_DEFAULT_TRIAL_HOURS = 24
# Panel statuses that make a trial TERMINAL on their own (delete the account + reset to available).
# LIMITED is deliberately EXCLUDED: a data-exhausted trial whose TIME is still valid stays live so a
# referral traffic bump can revive the same config — it becomes terminal only once its time also
# passes (the expires_at check in _is_expired), never on data-exhaustion alone.
_ENDED_STATUSES = {"EXPIRED", "DISABLED"}


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
    """The rolling claim cooldown (``trial_hours`` since the last claim) hasn't elapsed yet.

    ``retry_after`` is the human time LEFT until the next claim is allowed ("7h 12m"), or "" when
    it can't be derived (the message then falls back to a generic wait copy).
    """

    retry_after: str = ""


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
    """Rendered tokens for the status screen (``active`` controls the change-location button).

    ``data_exhausted`` is True for a live-but-data-spent trial (LIMITED, time still valid): the
    config landing then shows the 'invite to revive' copy instead of the healthy 'active' copy.
    """

    tg_id: int
    referrals: int
    daily_limit: str
    configs: int
    usage: str
    remaining: str
    active: bool
    data_exhausted: bool = False


@dataclass(frozen=True)
class Delivery:
    """A single delivered config: the location name, its link, and the time LEFT ("19h 54m")."""

    location: str
    link: str
    expires: str  # human time-remaining, not an absolute date


@dataclass(frozen=True)
class _Cached:
    """The cached subscription map backing the picker + link lookups for one user."""

    links: dict[str, str]
    expires: str | None


def start_of_today_utc() -> datetime:
    """Midnight UTC today — the boundary for the calendar-day admin stats (configs/new today)."""
    now = datetime.now(UTC)
    return now.replace(hour=0, minute=0, second=0, microsecond=0)


def cooldown_start(hours: int) -> datetime:
    """Start of the rolling claim-cooldown window: ``now - hours``.

    The claim guard counts a user's claims at/after this instant — so a user can claim again only
    once ``trial_hours`` have elapsed since their LAST claim (not at the next UTC midnight, which
    let a near-midnight claimer re-claim minutes later).
    """
    return datetime.now(UTC) - timedelta(hours=max(hours, 1))


def cooldown_remaining(last_claim: datetime | None, hours: int) -> str:
    """Human time LEFT until the cooldown elapses (``last_claim + hours``); "—" when unknown.

    Shared by the claim guard's "try again in …" copy and the limit/expiry reminders, so the wait
    shown to the user is always derived from their real last-claim time, never a hardcoded "24h".
    """
    if last_claim is None:
        return "—"
    if last_claim.tzinfo is None:
        last_claim = last_claim.replace(tzinfo=UTC)
    return _human_duration(last_claim + timedelta(hours=max(hours, 1)) - datetime.now(UTC))


def in_cooldown(last_claim: datetime | None, hours: int) -> bool:
    """True while the rolling claim cooldown is still active (last claim less than ``hours`` ago).

    The single predicate behind the claim guard — a claim exactly ``hours`` old no longer blocks, so
    the user can re-claim the instant their trial expires (both anchored to the same claim time).
    """
    if last_claim is None:
        return False
    if last_claim.tzinfo is None:
        last_claim = last_claim.replace(tzinfo=UTC)
    return last_claim > cooldown_start(hours)


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


def human_remaining(value: str | None) -> str:
    """Time LEFT until ``value`` (an ISO expiry) as a human duration ("19h 54m"); "—" if unknown.

    Owners want the validity shown as time-remaining, not an absolute date — the same format the
    status screen already uses for ``{remaining}``.
    """
    parsed = _parse_dt(value)
    return _human_duration(parsed - datetime.now(UTC)) if parsed else "—"


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
        """Terminal (delete + reset) test: missing, EXPIRED/DISABLED, or TIME past. A LIMITED trial
        whose ``expires_at`` is still in the future is NOT terminal — it stays live + revivable."""
        if not sub.is_found:
            return True
        if sub.user.user_status.upper() in _ENDED_STATUSES:
            return True
        expires = _parse_dt(sub.user.expires_at)
        return expires is not None and expires <= datetime.now(UTC)

    @staticmethod
    def _panel_user_terminal(user: PanelUser) -> bool:
        """Terminal (delete + reset) test on the AUTHORITATIVE user record
        (``GET /users/by-username`` -> ``status`` + ``expireAt``): EXPIRED / DISABLED, or the
        expiry time has passed. A LIMITED user whose time is valid is NOT terminal (kept/revivable).

        The background reconcile sweep uses THIS instead of ``_is_expired`` (which reads the
        subscription endpoint): a terminal trial has no active links, so ``subscription()`` falls
        through to the raw-config endpoint whose failure would mask the expiry. Reading the user
        record needs a single call, never touches links, and its ``status`` is the source of
        truth."""
        if user.status.upper() in _ENDED_STATUSES:
            return True
        expires = _parse_dt(user.expire_at)
        return expires is not None and expires <= datetime.now(UTC)

    @staticmethod
    def _is_data_exhausted(sub: Subscription) -> bool:
        """A live trial whose DATA is spent (panel LIMITED, or used >= limit) but whose time is
        still valid — revivable by a referral bump, so screens surface it apart from healthy."""
        if sub.user.user_status.upper() == "LIMITED":
            return True
        limit = sub.user.traffic_limit_bytes
        return limit > 0 and sub.user.traffic_used_bytes >= limit

    async def _reset(self, user: User) -> None:
        # Delete the ended trial's panel account so expired users don't accumulate in Remnawave (the
        # panel only DISABLES an expired user, never removes it). Best-effort + bounded: a 404 means
        # it's already gone, and a transient error is logged and ignored so the reset still happens.
        username = user.panel_username
        if username:
            try:
                await self._panel.delete_user_by_username(username)
            except RemnawaveError:
                logger.warning("self-heal: panel delete failed for %s", user.telegram_id)
        user.status = UserStatus.available
        user.panel_username = None
        await self._clear_cache(user.telegram_id)
        await self._redis.delete(limited_notified_key(user.telegram_id))

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

    async def _last_claim_at(self, user: User) -> datetime | None:
        """The rolling-cooldown anchor: when the user last PROVISIONED a trial.

        Prefers the durable ``last_claim_at`` (set at provision, so it lines up with the trial's own
        expiry); falls back to the newest delivered-config time for a user whose field is still
        unset (the migration backfills existing rows, so this only covers a pre-backfill edge)."""
        if user.last_claim_at is not None:
            return user.last_claim_at
        return await self._config_log_repo.latest_created_at_for_user(user.telegram_id)

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

        # 2. One claim per rolling `trial_hours` window (keyed off the user's LAST claim, so
        #    exhausting the quota never lets them re-claim before the cooldown elapses). The anchor
        #    is the PROVISION time (last_claim_at), so the window ends exactly when the trial does.
        hours = max(await self._settings.get_int(SettingKey.TRIAL_HOURS, _DEFAULT_TRIAL_HOURS), 1)
        last_claim = await self._last_claim_at(user)
        if in_cooldown(last_claim, hours):
            return AlreadyClaimedToday(cooldown_remaining(last_claim, hours))

        # 3. Trial squad configured (first-run wizard done)?
        squad = await self._settings.get(SettingKey.TRIAL_SQUAD)
        if not squad:
            return NotReady()

        # 4. Panel call 1 — create a fresh trial user. User stays `available` on failure. `claim_at`
        #    is the shared anchor: the panel account expires at claim_at + hours, and so does the
        #    cooldown (persisted at step 6), so the two can never drift apart.
        traffic_bytes = await compute_traffic_bytes(self._settings, user.referral_count)
        claim_at = datetime.now(UTC)
        expire_at = claim_at + timedelta(hours=hours)
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
        await self._redis.delete(limited_notified_key(user.telegram_id))  # fresh episode
        user.status = UserStatus.active_config
        user.panel_username = username
        user.last_claim_at = claim_at  # cooldown starts at provision, aligned with the panel expiry
        return Provisioned(list(filtered.keys()), human_bytes(traffic_bytes))

    async def status(self, user: User) -> StatusInfo | PanelError:
        usage, remaining, active, exhausted = "—", "—", False, False
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
                exhausted = self._is_data_exhausted(sub)
        daily_limit = human_bytes(await compute_traffic_bytes(self._settings, user.referral_count))
        return StatusInfo(
            tg_id=user.telegram_id,
            referrals=user.referral_count,
            daily_limit=daily_limit,
            configs=await self._config_log_repo.count_for_user(user.telegram_id),
            usage=usage,
            remaining=remaining,
            active=active,
            data_exhausted=exhausted,
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
        return Delivery(name, cached.links[name], human_remaining(cached.expires))
