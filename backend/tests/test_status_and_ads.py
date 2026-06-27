"""Status body composition (received line + conditional usage block) and the gated ads queueing.

Pure helpers over fakeredis-backed content/settings — no DB.
"""

from __future__ import annotations

import json

import fakeredis.aioredis

from gozar.bot.handlers.config import _maybe_queue_ads
from gozar.bot.handlers.status import _status_body
from gozar.bot.notifications import PendingNotifications
from gozar.cache.redis import SETTINGS_KEY
from gozar.db.models.enums import Language
from gozar.db.models.user import User
from gozar.services.content import ContentService
from gozar.services.settings_service import SettingKey, SettingsService
from gozar.services.trial import StatusInfo

_STATUS_TMPL = "status:{status_line}|configs={configs}{status_usage}"


async def _content(**entries: str) -> ContentService:
    redis = fakeredis.aioredis.FakeRedis(decode_responses=True)
    for key, body in entries.items():
        await redis.set(key, body)
    return ContentService(None, redis)  # type: ignore[arg-type]  # session unused on a cache hit


def _info(*, active: bool) -> StatusInfo:
    return StatusInfo(
        tg_id=1,
        referrals=0,
        daily_limit="1.0 GB",
        configs=3 if active else 0,
        usage="100 MB",
        remaining="5h",
        active=active,
    )


async def test_status_body_active_shows_received_line_and_usage() -> None:
    content = await _content(
        **{
            "cache:content:en:status": _STATUS_TMPL,
            "cache:content:en:status_received": "RECEIVED",
            "cache:content:en:status_usage": "|usage={usage}|left={remaining}",
        }
    )
    body = await _status_body(_info(active=True), content, Language.en)
    assert "RECEIVED" in body
    assert "usage=100 MB|left=5h" in body  # usage block present + tokens filled


async def test_status_body_claimable_hides_usage() -> None:
    content = await _content(
        **{
            "cache:content:en:status": _STATUS_TMPL,
            "cache:content:en:status_not_received": "NOT-RECEIVED",
            "cache:content:en:status_usage": "|usage={usage}",  # seeded but must not be used
        }
    )
    body = await _status_body(_info(active=False), content, Language.en)
    assert "NOT-RECEIVED" in body
    assert "usage=" not in body  # no usage block when claimable


async def _settings(*, ads_enabled: bool) -> SettingsService:
    redis = fakeredis.aioredis.FakeRedis(decode_responses=True)
    await redis.set(
        SETTINGS_KEY, json.dumps({SettingKey.ADS_ENABLED: "true" if ads_enabled else "false"})
    )
    return SettingsService(None, redis)  # type: ignore[arg-type]


class _Bot:
    def __init__(self) -> None:
        self.sent: list[tuple[int, str]] = []

    async def send_message(self, chat_id: int, text: str, reply_markup=None) -> None:
        self.sent.append((chat_id, text))


async def test_ads_queued_when_enabled() -> None:
    settings = await _settings(ads_enabled=True)
    content = await _content(**{"cache:content:en:ads": "AD"})
    notify = PendingNotifications()
    user = User(telegram_id=5, language=Language.en)

    await _maybe_queue_ads(settings, content, notify, user)
    bot = _Bot()
    await notify.flush(bot)
    assert bot.sent == [(5, "AD")]  # a separate ads message, queued for post-commit flush


async def test_ads_not_queued_when_disabled() -> None:
    settings = await _settings(ads_enabled=False)
    content = await _content(**{"cache:content:en:ads": "AD"})
    notify = PendingNotifications()
    user = User(telegram_id=5, language=Language.en)

    await _maybe_queue_ads(settings, content, notify, user)
    bot = _Bot()
    await notify.flush(bot)
    assert bot.sent == []  # gated off -> nothing queued
