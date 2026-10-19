"""The look's state: the 🎨 switches (settings table) and what Telegram taught us (Redis), shared
by the app and the worker — and the worker's daily check of the premium emoji ids."""

from __future__ import annotations

import json
from types import SimpleNamespace

import fakeredis.aioredis

from gozar.cache.redis import SETTINGS_KEY
from gozar.services.look import LOOK_BLOCKED_KEY, LookService
from gozar.services.settings_service import SettingKey, SettingsService
from gozar.ui import icons
from gozar.worker.tasks import verify_premium_emoji


def _redis():
    return fakeredis.aioredis.FakeRedis(decode_responses=True)


async def test_both_switches_read_as_on_until_set() -> None:
    redis = _redis()
    await redis.set(SETTINGS_KEY, json.dumps({}))  # the settings table, with neither key in it
    look = await LookService(SettingsService(None, redis), redis).snapshot()  # type: ignore[arg-type]
    assert look.premium and look.rich and look.icons_on


async def test_switches_come_from_the_settings_table() -> None:
    redis = _redis()
    await redis.set(SETTINGS_KEY, json.dumps({SettingKey.LOOK_PREMIUM: "false"}))
    look = await LookService(SettingsService(None, redis), redis).snapshot()  # type: ignore[arg-type]
    assert not look.premium and look.rich and not look.icons_on


async def test_a_refusal_blocks_icons_once_and_leaves_one_notice() -> None:
    redis = _redis()
    looks = LookService(None, redis)
    await looks.refused("Bad Request: DOCUMENT_INVALID")
    await looks.refused("second reason")  # the first reason is the one 🎨 shows
    look = await looks.snapshot()
    assert look.blocked and not look.icons_on
    assert await looks.blocked_reason() == "Bad Request: DOCUMENT_INVALID"
    assert 0 < await redis.ttl(LOOK_BLOCKED_KEY) <= 24 * 3600  # it ends by itself
    assert await looks.take_notice() == "blocked"
    assert await looks.take_notice() is None  # shown once


async def test_kept_and_retry_lift_the_block() -> None:
    redis = _redis()
    looks = LookService(None, redis)
    await looks.refused("x")
    await looks.kept()
    assert not (await looks.snapshot()).blocked
    await looks.refused("y")
    await looks.retry()
    assert not (await looks.snapshot()).blocked and await looks.take_notice() is None


async def test_the_daily_check_records_the_ids_telegram_no_longer_knows() -> None:
    redis = _redis()
    every = sorted(icons.all_ids())
    gone = {every[0], every[250]}
    calls: list[int] = []

    async def get_custom_emoji_stickers(ids: list[str]):  # noqa: ANN202
        calls.append(len(ids))
        return [SimpleNamespace(custom_emoji_id=i) for i in ids if i not in gone]

    bot = SimpleNamespace(get_custom_emoji_stickers=get_custom_emoji_stickers)
    await verify_premium_emoji({"bot": bot, "cache_redis": redis})
    assert calls == [200, 200, 3]  # Telegram takes at most 200 ids per call
    looks = LookService(None, redis)
    look = await looks.snapshot()
    assert look.missing == frozenset(gone)
    assert look.usable(every[0]) is None and look.usable(every[1]) == every[1]
    checked = await looks.checked()
    assert checked is not None and checked[1] == 2


async def test_a_failed_check_keeps_the_previous_answer() -> None:
    redis = _redis()
    await LookService(None, redis).record_missing({"123"})

    async def broken(ids: list[str]):  # noqa: ANN202
        raise RuntimeError("telegram down")

    await verify_premium_emoji(
        {"bot": SimpleNamespace(get_custom_emoji_stickers=broken), "cache_redis": redis}
    )
    assert (await LookService(None, redis).snapshot()).missing == frozenset({"123"})
