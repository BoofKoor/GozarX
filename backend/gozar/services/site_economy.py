"""Website trial economics — the site's quota math, driven entirely by the ``site_*`` settings.

The site analogue of ``trial.compute_traffic_bytes``: it reads the ``site_*`` keys (NOT the bot's),
so the two economies are fully independent. This is the single source of the site quota — reused by
site claim flow (P3), the referral live-bump (P5), and the status "next allowance" quote (P4). Never
hardcodes a reward/cap; every number comes from settings.
"""

from __future__ import annotations

from collections.abc import Collection, Sequence
from datetime import UTC, datetime, timedelta

from gozar.db.models.site_device import SiteDevice
from gozar.db.models.site_reward import SiteRewardType
from gozar.db.repositories.site_reward import SiteRewardRepository
from gozar.services.settings_service import SettingsService, SiteSettingKey

# Fallbacks used ONLY if the (seeded) setting is missing — not a place to encode economics.
_DEFAULT_SITE_DAILY_MB = 1024
_MB = 1024 * 1024


async def site_compute_traffic_bytes(
    settings: SettingsService,
    referral_count: int,
    *,
    rewards: Collection[str] = (),
    streak_active: bool = False,
) -> int:
    """Site daily allowance in bytes: base + capped referral bonus + claimed one-time rewards
    (PWA / notifications) + the standing daily-streak bonus.

    ``rewards`` is the set of one-time reward types the device has already claimed
    (``SiteRewardType.pwa`` / ``.push``); ``streak_active`` adds the streak bonus while the device
    is on a qualifying streak. All amounts come from the ``site_*`` settings.
    """
    daily_mb = await settings.get_int(SiteSettingKey.SITE_DAILY_LIMIT_MB, _DEFAULT_SITE_DAILY_MB)
    reward_mb = await settings.get_int(SiteSettingKey.SITE_REFERRAL_REWARD_MB, 0)
    cap = await settings.get_int(SiteSettingKey.SITE_REFERRAL_REWARD_LIMIT, 0)
    rewarded = min(max(referral_count, 0), max(cap, 0))
    total_mb = daily_mb + rewarded * reward_mb

    if SiteRewardType.pwa in rewards:
        total_mb += await settings.get_int(SiteSettingKey.SITE_REWARD_PWA_MB, 0)
    if SiteRewardType.push in rewards:
        total_mb += await settings.get_int(SiteSettingKey.SITE_REWARD_PUSH_MB, 0)
    if streak_active:
        total_mb += await settings.get_int(SiteSettingKey.SITE_REWARD_STREAK_MB, 0)

    return total_mb * _MB


def streak_is_active(streak_count: int, streak_days: int) -> bool:
    """Whether a daily-claim streak has reached the qualifying length."""
    return streak_days > 0 and streak_count >= streak_days


def _aware(dt: datetime) -> datetime:
    return dt if dt.tzinfo else dt.replace(tzinfo=UTC)


def streak_from_claim_times(
    claim_times: Sequence[datetime], trial_hours: int, now: datetime
) -> int:
    """The consecutive-daily-claim streak DERIVED from the claim log — the single source of truth.

    ``claim_times`` are all of a device's ``site_claims`` timestamps (any order). Because a claim is
    only *provisioned* once per rolling ``trial_hours`` window — a change-location within that
    window logs another row but is the SAME day's config — we first collapse claims into
    provision-days (the first claim of each window), then count the trailing run of consecutive
    days, where "next day" means within one extra window of grace (2×``trial_hours``). A longer gap
    ends the run.

    The streak only counts while it is still LIVE: if the last provision-day is itself older than
    the grace window relative to ``now``, the streak has lapsed (the next claim would restart it at
    1), so we report 0 — keeping the shown streak and its bonus honest about what a claim grants.

    Deriving from the log (not a stored counter) keeps the value self-consistent with the history
    the user sees and self-healing for any row whose counter was never written (e.g. a config
    provisioned before streaks existed): the claims themselves are the record.
    """
    if not claim_times:
        return 0
    hours = max(trial_hours, 1)
    window = timedelta(hours=hours)  # one claim per this window — within it is the same day
    grace = timedelta(hours=hours * 2)  # a claim within one extra window continues the streak
    ordered = sorted(_aware(t) for t in claim_times)
    # Collapse to provision-days: keep only the first claim of each cooldown window.
    days = [ordered[0]]
    for t in ordered[1:]:
        if t - days[-1] > window:
            days.append(t)
    if now - days[-1] > grace:
        return 0  # lapsed — the next claim would restart the streak
    streak = 1
    newest_first = list(reversed(days))
    for newer, older in zip(newest_first, newest_first[1:], strict=False):
        if newer - older <= grace:
            streak += 1
        else:
            break
    return streak


async def site_device_allowance_bytes(
    settings: SettingsService, device: SiteDevice, reward_repo: SiteRewardRepository
) -> int:
    """A device's FULL current daily allowance for a LIVE-BUMP (referral credit / reward claim):
    base + capped referral bonus + its claimed one-time rewards + the standing streak bonus.

    Uses the device's stored ``streak_count`` — kept in sync on every provision by ``claim`` — since
    the bump paths don't carry the claim log. The visible streak (status) and the provisioned streak
    (claim) are derived straight from that log via ``streak_from_claim_times``."""
    rewards = await reward_repo.types_for_device(device.uuid)
    streak_days = await settings.get_int(SiteSettingKey.SITE_STREAK_DAYS, 0)
    return await site_compute_traffic_bytes(
        settings,
        device.referral_count,
        rewards=rewards,
        streak_active=streak_is_active(device.streak_count, streak_days),
    )
