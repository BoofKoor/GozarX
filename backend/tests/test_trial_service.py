"""TrialService: provisioning, the DB-status-flip-LAST ordering, self-heal, daily guard, by-name
link matching, capped referral traffic, and status. DB-gated (real session + repos) with fakeredis
and a ``FakePanel`` stub standing in for the live Remnawave client.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta

import fakeredis.aioredis
import pytest

from gozar.cache.redis import SETTINGS_KEY
from gozar.db.models.config_log import ConfigLog
from gozar.db.models.enums import UserStatus
from gozar.db.models.user import User
from gozar.db.repositories.config_log import ConfigLogRepository
from gozar.remnawave.errors import RemnawaveError
from gozar.remnawave.schemas import PanelUser, Subscription, SubscriptionUser
from gozar.services.settings_service import SettingKey, SettingsService
from gozar.services.trial import (
    AlreadyActive,
    AlreadyClaimedToday,
    NoLocations,
    NotReady,
    PanelError,
    Provisioned,
    TrialService,
    start_of_today_utc,
)

_BASE_SETTINGS = {
    SettingKey.TRIAL_SQUAD: "sq1",
    SettingKey.LOCATIONS: "",  # empty allowlist -> keep all
    SettingKey.DAILY_LIMIT_MB: "1024",
    SettingKey.REFERRAL_REWARD_MB: "500",
    SettingKey.REFERRAL_REWARD_LIMIT: "10",
    SettingKey.TRIAL_HOURS: "24",
}


def _iso(delta_hours: float) -> str:
    return (datetime.now(UTC) + timedelta(hours=delta_hours)).isoformat()


def _sub(
    *, status: str = "ACTIVE", expires_hours: float = 12, used: int = 0, is_found: bool = True
) -> Subscription:
    return Subscription(
        is_found=is_found,
        user=SubscriptionUser(
            user_status=status,
            expires_at=_iso(expires_hours),
            traffic_used_bytes=used,
            traffic_limit_bytes=1024 * 1024 * 1024,
            short_uuid="su1",
        ),
    )


class FakePanel:
    """Stands in for RemnawaveClient. ``sub_queue`` items are returned in order (last one repeats);
    an item that is an Exception is raised, letting a test sequence e.g. [404, live]."""

    def __init__(self, sub_queue: list, *, create_error: Exception | None = None) -> None:
        self.sub_queue = sub_queue
        self._idx = 0
        self.create_error = create_error
        self.created: list[tuple] = []
        self.sub_calls: list[str] = []

    async def create_trial_user(self, username, traffic_bytes, expire_at, squad_uuids) -> PanelUser:
        self.created.append((username, traffic_bytes, expire_at, squad_uuids))
        if self.create_error is not None:
            raise self.create_error
        return PanelUser(uuid="u1", username=username)

    async def subscription(self, username: str):
        self.sub_calls.append(username)
        item = self.sub_queue[self._idx]
        if self._idx < len(self.sub_queue) - 1:
            self._idx += 1
        if isinstance(item, Exception):
            raise item
        return item


async def _service(session, panel, **overrides) -> TrialService:
    redis = fakeredis.aioredis.FakeRedis(decode_responses=True)
    await redis.set(SETTINGS_KEY, json.dumps({**_BASE_SETTINGS, **overrides}))
    return TrialService(panel, SettingsService(session, redis), ConfigLogRepository(session), redis)


async def _user(session, **kw) -> User:
    user = User(telegram_id=kw.pop("telegram_id", 100), **kw)
    session.add(user)
    await session.flush()
    return user


async def _log_at(session, user_id: int, *, hours_ago: float) -> None:
    """Insert a claim with an explicit ``created_at`` (the rolling cooldown is keyed off it)."""
    log = ConfigLog(
        user_id=user_id,
        location="Germany",
        created_at=datetime.now(UTC) - timedelta(hours=hours_ago),
    )
    session.add(log)
    await session.flush()


_TWO = {"Germany": "vless://de#Germany", "Finland": "vless://fi#Finland"}


async def test_claim_provisions_and_caches(session) -> None:
    panel = FakePanel([(_sub(), _TWO)])
    trial = await _service(session, panel)
    user = await _user(session)

    result = await trial.claim(user)

    assert isinstance(result, Provisioned)
    assert result.remarks == ["Germany", "Finland"]
    assert result.size == "1.0 GB"
    assert user.status is UserStatus.active_config
    assert user.panel_username == panel.created[0][0]  # the freshly created username
    assert panel.created[0][1] == 1024 * 1024 * 1024  # daily allowance, no referrals
    assert panel.created[0][3] == ["sq1"]


async def test_claim_create_failure_leaves_user_available(session) -> None:
    panel = FakePanel([(_sub(), _TWO)], create_error=RemnawaveError("boom"))
    trial = await _service(session, panel)
    user = await _user(session)

    result = await trial.claim(user)

    assert isinstance(result, PanelError)
    assert user.status is UserStatus.available  # status flip is LAST — never half-committed
    assert user.panel_username is None


async def test_claim_empty_links_is_no_locations_no_flip(session) -> None:
    panel = FakePanel([(_sub(), {})])  # subscription carried no usable links
    trial = await _service(session, panel)
    user = await _user(session)

    result = await trial.claim(user)

    assert isinstance(result, NoLocations)
    assert user.status is UserStatus.available
    assert user.panel_username is None


async def test_claim_allowlist_intersects_empty_is_no_locations(session) -> None:
    panel = FakePanel([(_sub(), _TWO)])
    trial = await _service(session, panel, **{SettingKey.LOCATIONS: "Sweden"})  # excludes DE/FI
    user = await _user(session)

    assert isinstance(await trial.claim(user), NoLocations)
    assert user.status is UserStatus.available


async def test_claim_not_ready_without_squad(session) -> None:
    panel = FakePanel([(_sub(), _TWO)])
    trial = await _service(session, panel, **{SettingKey.TRIAL_SQUAD: ""})
    user = await _user(session)

    assert isinstance(await trial.claim(user), NotReady)
    assert not panel.created  # no panel call when not configured


async def test_claim_cooldown_guard_blocks_within_window(session) -> None:
    panel = FakePanel([(_sub(), _TWO)])
    trial = await _service(session, panel)
    user = await _user(session)
    await ConfigLogRepository(session).add(user.telegram_id, "Germany")  # claimed just now

    result = await trial.claim(user)
    assert isinstance(result, AlreadyClaimedToday)
    assert result.retry_after  # tells the user how long is left (≈ trial_hours)
    assert not panel.created


async def test_claim_cooldown_blocks_just_under_window(session) -> None:
    # The fix: the guard is a rolling `trial_hours` window keyed off the LAST claim, not the UTC
    # calendar day — so a claim 23h ago stays blocked (the near-midnight re-claim regression).
    panel = FakePanel([(_sub(), _TWO)])
    trial = await _service(session, panel)
    user = await _user(session)
    await _log_at(session, user.telegram_id, hours_ago=23)

    assert isinstance(await trial.claim(user), AlreadyClaimedToday)
    assert not panel.created


async def test_claim_cooldown_freed_after_window(session) -> None:
    # A claim older than `trial_hours` no longer blocks — the user can claim a fresh trial.
    panel = FakePanel([(_sub(), _TWO)])
    trial = await _service(session, panel)
    user = await _user(session)
    await _log_at(session, user.telegram_id, hours_ago=25)

    assert isinstance(await trial.claim(user), Provisioned)
    assert user.status is UserStatus.active_config


async def test_claim_already_active_when_live(session) -> None:
    panel = FakePanel([(_sub(), {"Germany": "vless://de#Germany"})])
    trial = await _service(session, panel)
    user = await _user(session, status=UserStatus.active_config, panel_username="g100_old")

    result = await trial.claim(user)

    assert isinstance(result, AlreadyActive)
    assert result.remarks == ["Germany"]
    assert user.status is UserStatus.active_config
    assert not panel.created  # reused the live trial; no new panel user


async def test_claim_transient_error_on_active_keeps_state(session) -> None:
    panel = FakePanel([RemnawaveError("503", status_code=503)])
    trial = await _service(session, panel)
    user = await _user(session, status=UserStatus.active_config, panel_username="g100_old")

    result = await trial.claim(user)

    assert isinstance(result, PanelError)
    assert user.status is UserStatus.active_config  # transient -> no self-heal, no state change
    assert user.panel_username == "g100_old"


@pytest.mark.parametrize(
    "ended",
    [
        (_sub(status="EXPIRED"), _TWO),
        (_sub(status="LIMITED"), _TWO),
        (_sub(is_found=False), _TWO),
        (_sub(expires_hours=-1), _TWO),  # expireAt in the past
        RemnawaveError("404", status_code=404),  # panel user gone
    ],
)
async def test_self_heal_then_reclaim(session, ended) -> None:
    # First subscription() call (the self-heal refresh) reports an ended/missing trial; after the
    # reset + fresh create, the second call returns a live subscription.
    panel = FakePanel([ended, (_sub(), _TWO)])
    trial = await _service(session, panel)
    user = await _user(session, status=UserStatus.active_config, panel_username="g100_old")

    result = await trial.claim(user)

    assert isinstance(result, Provisioned)  # healed, then re-claimed
    assert user.status is UserStatus.active_config
    assert user.panel_username == panel.created[0][0]
    assert user.panel_username != "g100_old"  # a brand-new panel user
    assert len(panel.created) == 1


async def test_link_for_matches_by_name(session) -> None:
    panel = FakePanel([(_sub(), _TWO)])
    trial = await _service(session, panel)
    user = await _user(session)
    await trial.claim(user)

    first = await trial.link_for(user, 0)
    second = await trial.link_for(user, 1)
    assert (first.location, first.link) == ("Germany", "vless://de#Germany")
    assert (second.location, second.link) == ("Finland", "vless://fi#Finland")
    assert await trial.link_for(user, 9) is None  # out of range


async def test_locations_served_from_cache(session) -> None:
    panel = FakePanel([(_sub(), _TWO)])
    trial = await _service(session, panel)
    user = await _user(session)
    await trial.claim(user)  # one subscription() call

    locations = await trial.locations(user)
    assert locations == ["Germany", "Finland"]
    assert len(panel.sub_calls) == 1  # served from cache — no extra panel call


async def test_traffic_includes_capped_referral_bonus(session) -> None:
    panel = FakePanel([(_sub(), _TWO)])
    trial = await _service(session, panel)
    user = await _user(session, referral_count=25)  # cap is 10

    await trial.claim(user)
    # (1024 daily + min(25,10)*500 bonus) MB = 6024 MB — capped, never 25*500.
    assert panel.created[0][1] == 6024 * 1024 * 1024


async def test_status_active_reports_usage_and_change(session) -> None:
    panel = FakePanel([(_sub(used=500 * 1024 * 1024, expires_hours=12), _TWO)])
    trial = await _service(session, panel)
    user = await _user(session, status=UserStatus.active_config, panel_username="g100_live")

    info = await trial.status(user)

    assert not isinstance(info, PanelError)
    assert info.active is True
    assert info.usage == "500.0 MB"
    assert info.daily_limit == "1.0 GB"
    assert "h" in info.remaining  # time left, not data


async def test_status_inactive_user(session) -> None:
    panel = FakePanel([(_sub(), _TWO)])
    trial = await _service(session, panel)
    user = await _user(session)  # available, no panel user

    info = await trial.status(user)

    assert not isinstance(info, PanelError)
    assert info.active is False
    assert info.usage == "—"
    assert info.remaining == "—"
    assert info.daily_limit == "1.0 GB"


async def test_status_self_heals_expired_active(session) -> None:
    panel = FakePanel([(_sub(status="EXPIRED"), _TWO)])
    trial = await _service(session, panel)
    user = await _user(session, status=UserStatus.active_config, panel_username="g100_old")

    info = await trial.status(user)

    assert not isinstance(info, PanelError)
    assert info.active is False
    assert user.status is UserStatus.available  # status read self-healed the ended trial
    assert user.panel_username is None


def test_start_of_today_utc_is_midnight() -> None:
    midnight = start_of_today_utc()
    assert (midnight.hour, midnight.minute, midnight.second, midnight.microsecond) == (0, 0, 0, 0)
    assert midnight.tzinfo is UTC
