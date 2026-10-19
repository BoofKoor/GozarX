"""Premium location flags on the users' side: the picker draws each flag as a button icon, and a
Telegram refusal falls back to the picker exactly as it always was — a flag never costs a user
their picker or their config."""

from __future__ import annotations

from types import SimpleNamespace

import fakeredis.aioredis
from aiogram.exceptions import TelegramBadRequest
from aiogram.methods import EditMessageText
from aiogram.types import Message

from gozar.bot import callbacks as cb
from gozar.bot.handlers.config import _edit_flagged, _picker_flags, _render_claim
from gozar.bot.keyboards import location_keyboard
from gozar.bot.notifications import PendingNotifications
from gozar.db.models.enums import Language
from gozar.db.models.user import User
from gozar.services.content import ContentService
from gozar.services.trial import Provisioned
from gozar.ui import icons
from gozar.ui.buttons import EMPTY_OVERRIDES
from gozar.ui.look import PLAIN, Look

REMARKS = ["🇩🇪 آلمان", "هلند", "WARP"]


class FakeLooks:
    def __init__(self, look: Look) -> None:
        self._look = look
        self.refusals: list[str] = []

    async def snapshot(self) -> Look:
        return self._look

    async def refused(self, reason: str) -> None:
        self.refusals.append(reason)


def _screen(refuse_icons: bool) -> Message:
    markups: list[object] = []

    async def edit_text(text: str, reply_markup=None, **kw: object) -> None:  # noqa: ANN001
        markups.append(reply_markup)
        has_icon = any(b.icon_custom_emoji_id for row in reply_markup.inline_keyboard for b in row)
        if refuse_icons and has_icon:
            raise TelegramBadRequest(
                method=EditMessageText(text="x"), message="Bad Request: DOCUMENT_INVALID"
            )

    msg = Message.model_construct(message_id=1, chat=None, date=None)
    object.__setattr__(msg, "edit_text", edit_text)
    object.__setattr__(msg, "markups", markups)
    return msg


def _picker() -> object:
    return location_keyboard(REMARKS, cb.CONFIG_CLAIM_PREFIX, Language.fa)


async def test_the_picker_draws_flags_as_premium_icons() -> None:
    screen = _screen(refuse_icons=False)
    looks = FakeLooks(Look())
    flags = _picker_flags(REMARKS, cb.CONFIG_CLAIM_PREFIX)
    await _edit_flagged(SimpleNamespace(message=screen), "pick", _picker(), flags, looks)
    (markup,) = screen.markups
    row = markup.inline_keyboard[0]
    assert (row[0].text, row[0].icon_custom_emoji_id) == ("آلمان", icons.FLAGS["DE"])
    assert (row[1].text, row[1].icon_custom_emoji_id) == ("هلند", icons.FLAGS["NL"])
    assert markup.inline_keyboard[1][0].icon_custom_emoji_id is None  # WARP names no country
    assert looks.refusals == []


async def test_a_refused_flag_falls_back_to_the_plain_picker() -> None:
    screen = _screen(refuse_icons=True)
    looks = FakeLooks(Look())
    plain = _picker()
    flags = _picker_flags(REMARKS, cb.CONFIG_CLAIM_PREFIX)
    await _edit_flagged(SimpleNamespace(message=screen), "pick", plain, flags, looks)
    assert len(screen.markups) == 2 and screen.markups[1] is plain
    assert screen.markups[1].inline_keyboard[0][0].text == "🇩🇪 آلمان"  # exactly the remark
    assert looks.refusals == ["Telegram server says - Bad Request: DOCUMENT_INVALID"]


async def test_with_icons_off_the_picker_is_sent_once_as_it_always_was() -> None:
    screen = _screen(refuse_icons=False)
    plain = _picker()
    flags = _picker_flags(REMARKS, cb.CONFIG_CLAIM_PREFIX)
    await _edit_flagged(SimpleNamespace(message=screen), "pick", plain, flags, FakeLooks(PLAIN))
    assert screen.markups == [plain]


async def test_a_claim_hands_back_the_picker_with_its_flags() -> None:
    redis = fakeredis.aioredis.FakeRedis(decode_responses=True)
    await redis.set("cache:content:fa:choose_location", "pick")
    content = ContentService(None, redis)  # type: ignore[arg-type]
    user = User(telegram_id=1, language=Language.fa)
    result = Provisioned(remarks=REMARKS, size="1 GB")
    text, markup, flags = await _render_claim(result, user, content, EMPTY_OVERRIDES, 8)
    assert text == "pick"
    assert flags == {f"{cb.CONFIG_CLAIM_PREFIX}{i}": r for i, r in enumerate(REMARKS)}


async def test_the_delivered_config_falls_back_to_its_plain_text() -> None:
    seen: list[tuple[str, object]] = []
    refusals: list[str] = []

    async def edit_text(text: str, reply_markup=None, **kw: object) -> None:  # noqa: ANN001
        seen.append((text, reply_markup))
        if "tg-emoji" in text:
            raise TelegramBadRequest(method=EditMessageText(text="x"), message="Bad Request: nope")

    async def on_fallback(reason: str) -> None:
        refusals.append(reason)

    notify = PendingNotifications()
    notify.edit(
        SimpleNamespace(edit_text=edit_text),
        '<tg-emoji emoji-id="1">🇩🇪</tg-emoji> cfg',
        "KB",
        fallback_text="🇩🇪 cfg",
        on_fallback=on_fallback,
    )
    await notify.flush(None)
    assert seen == [('<tg-emoji emoji-id="1">🇩🇪</tg-emoji> cfg', "KB"), ("🇩🇪 cfg", "KB")]
    assert refusals == ["Telegram server says - Bad Request: nope"]
