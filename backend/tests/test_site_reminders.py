"""P7 — SiteReminderService: route a panel expiry/limit event to a device nudge (no push I/O here).

DB-gated with fakeredis + a tiny panel stub. Mirrors the bot ReminderService semantics: EXPIRED
self-heals the device to claimable; LIMITED keeps the account revivable and nudges once per episode.
"""

from __future__ import annotations

import json

import fakeredis.aioredis

from gozar.cache.redis import SETTINGS_KEY, site_limited_notified_key
from gozar.db.models.site_device import SiteDevice, SiteDeviceStatus
from gozar.db.repositories.site_device import SiteDeviceRepository
from gozar.remnawave.schemas import PanelUser, WebhookUserEvent
from gozar.services.settings_service import SettingsService, SiteSettingKey
from gozar.services.site_reminders import SiteReminderService

_SETTINGS = {SiteSettingKey.SITE_TRIAL_HOURS: "24"}


class _Panel:
    def __init__(self) -> None:
        self.deleted: list[str] = []

    async def delete_user_by_username(self, username: str) -> bool:
        self.deleted.append(username)
        return True


async def _redis() -> fakeredis.aioredis.FakeRedis:
    redis = fakeredis.aioredis.FakeRedis(decode_responses=True)
    await redis.set(SETTINGS_KEY, json.dumps(_SETTINGS))
    return redis


async def _device(session, **kw) -> SiteDevice:
    device = SiteDevice(uuid=kw.pop("uuid", "dev-1"), **kw)
    session.add(device)
    await session.flush()
    return device


def _svc(session, redis, panel) -> SiteReminderService:
    return SiteReminderService(
        SiteDeviceRepository(session), SettingsService(session, redis), redis, panel
    )


def _event(evt: str, username: str) -> WebhookUserEvent:
    return WebhookUserEvent(event=evt, data=PanelUser(username=username))


# --- webhook path -------------------------------------------------------------------------------


async def test_expired_event_self_heals_device(session) -> None:
    redis = await _redis()
    panel = _Panel()
    device = await _device(
        session, status=SiteDeviceStatus.active_config, site_panel_username="s-x"
    )
    await redis.set(site_limited_notified_key(device.uuid), "1")

    nudge = await _svc(session, redis, panel).apply_event(_event("user.expired", "s-x"))

    assert nudge is not None and nudge.title_key == "site_push_expired_title"
    assert device.status == SiteDeviceStatus.available
    assert device.site_panel_username is None
    assert panel.deleted == ["s-x"]  # panel trial freed
    assert await redis.get(site_limited_notified_key(device.uuid)) is None  # guard cleared


async def test_limited_event_keeps_account_and_nudges_once(session) -> None:
    redis = await _redis()
    panel = _Panel()
    device = await _device(
        session, status=SiteDeviceStatus.active_config, site_panel_username="s-x"
    )
    svc = _svc(session, redis, panel)

    first = await svc.apply_event(_event("user.limited", "s-x"))
    assert first is not None and first.title_key == "site_push_limited_title"
    # Account is KEPT (revivable by a bump) — no reset, no panel delete.
    assert device.status == SiteDeviceStatus.active_config
    assert device.site_panel_username == "s-x"
    assert panel.deleted == []

    # One-shot per episode: a second limited event is not nudged again.
    assert await svc.apply_event(_event("user.limited", "s-x")) is None


async def test_unknown_username_ignored(session) -> None:
    assert (
        await _svc(session, await _redis(), _Panel()).apply_event(_event("user.expired", "nobody"))
        is None
    )


async def test_blocked_device_ignored(session) -> None:
    redis = await _redis()
    await _device(session, status=SiteDeviceStatus.blocked, site_panel_username="s-b")
    assert await _svc(session, redis, _Panel()).apply_event(_event("user.expired", "s-b")) is None


async def test_non_nudge_event_ignored(session) -> None:
    # A non expiry/limit event returns before any DB lookup.
    assert (
        await _svc(session, await _redis(), _Panel()).apply_event(_event("user.created", "s-x"))
        is None
    )


# --- reconcile path -----------------------------------------------------------------------------


async def test_apply_ended_trial_resets_active_device(session) -> None:
    redis = await _redis()
    panel = _Panel()
    device = await _device(
        session, status=SiteDeviceStatus.active_config, site_panel_username="s-x"
    )
    nudge = await _svc(session, redis, panel).apply_ended_trial(device, {})
    assert nudge is not None and nudge.title_key == "site_push_expired_title"
    assert device.status == SiteDeviceStatus.available
    assert panel.deleted == ["s-x"]


async def test_apply_ended_trial_skips_non_active(session) -> None:
    redis = await _redis()
    device = await _device(session, status=SiteDeviceStatus.available)
    assert await _svc(session, redis, _Panel()).apply_ended_trial(device, {}) is None


async def test_reset_is_compare_and_swap(db_sessions) -> None:
    # A stale expiry teardown for "s-x" must NOT clobber a config the user re-claimed to "s-y" in
    # the read->write window: the CAS matches 0 rows, returns False, and leaves "s-y" as-is.
    from sqlalchemy import update

    from gozar.services.site_trial import reset_device_to_available

    redis = await _redis()
    async with db_sessions() as s0:
        s0.add(
            SiteDevice(
                uuid="dev-1", status=SiteDeviceStatus.active_config, site_panel_username="s-x"
            )
        )
        await s0.commit()

    async with db_sessions() as reset_s:
        device = await SiteDeviceRepository(reset_s).get("dev-1")  # loaded pointing at "s-x"
        # Concurrent re-claim swaps in a fresh account and commits BEFORE the teardown writes.
        async with db_sessions() as claim_s:
            await claim_s.execute(
                update(SiteDevice)
                .where(SiteDevice.uuid == "dev-1")
                .values(site_panel_username="s-y", status=SiteDeviceStatus.active_config)
            )
            await claim_s.commit()

        did_reset = await reset_device_to_available(_Panel(), redis, device)
        await reset_s.commit()

    assert did_reset is False  # guard missed — no clobber
    async with db_sessions() as s:
        row = await SiteDeviceRepository(s).get("dev-1")
    assert row.status == SiteDeviceStatus.active_config  # the re-claimed trial is intact
    assert row.site_panel_username == "s-y"
