"""Status screen render — the {referrals} (and the other) tokens must substitute, never appear
literally. Locks the shipped seed + handler against a regression where a token stops being passed.
"""

from __future__ import annotations

import fakeredis.aioredis

from gozar.bot.handlers.status import _status_body
from gozar.db.models.enums import Language
from gozar.seed import DEFAULT_CONTENT
from gozar.services.content import ContentService
from gozar.services.trial import StatusInfo

# The status body is composed from these content keys (the main template + its sub-blocks).
_STATUS_KEYS = ("status", "status_received", "status_not_received", "status_usage")


async def _content(lang: Language) -> ContentService:
    redis = fakeredis.aioredis.FakeRedis(decode_responses=True)
    for key in _STATUS_KEYS:
        await redis.set(f"cache:content:{lang.value}:{key}", DEFAULT_CONTENT[key][lang])
    return ContentService(None, redis)  # type: ignore[arg-type]  # session unused on a cache hit


async def test_status_body_substitutes_tokens_active() -> None:
    info = StatusInfo(
        tg_id=777,
        referrals=5,
        daily_limit="1.0 GB",
        configs=3,
        usage="100.0 MB",
        remaining="11h",
        active=True,
    )
    body = await _status_body(info, await _content(Language.fa), Language.fa)

    assert "{referrals}" not in body and "5" in body  # the referral count renders
    assert "{tg_id}" not in body and "777" in body
    assert "{status_line}" not in body and "{status_usage}" not in body  # sub-blocks substituted in
    assert "100.0 MB" in body  # the active usage block is included


async def test_status_body_substitutes_tokens_inactive() -> None:
    info = StatusInfo(
        tg_id=42,
        referrals=0,
        daily_limit="1.0 GB",
        configs=0,
        usage="—",
        remaining="—",
        active=False,
    )
    body = await _status_body(info, await _content(Language.en), Language.en)

    assert "{referrals}" not in body and "0" in body
    assert "{status_line}" not in body  # the not-received line is substituted in
    assert "{status_usage}" not in body  # empty for an inactive user, but never left as a token
