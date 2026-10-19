"""🎨 Appearance: the premium-emoji and rich-message switches, what Telegram said about them, a
self-test that sends samples to look at on the real app, and ``/simple`` (both off at once).

``/simple`` answers with a plain regular message on purpose: it is what an operator sends when the
screens do NOT render, so its own answer must not depend on anything that might be broken.
"""

from __future__ import annotations

import contextlib
from datetime import UTC, datetime

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from gozar.bot import callbacks as cb
from gozar.bot.handlers.admin.console import Console, keyboard
from gozar.db.models.enums import Language
from gozar.db.models.user import User
from gozar.services.look import LookService
from gozar.services.settings_service import SettingKey
from gozar.ui.buttons import ButtonOverrides
from gozar.ui.console_text import tr
from gozar.ui.fmt import num, when
from gozar.ui.look import PLAIN, Look
from gozar.ui.rich import Btn, Doc, esc

router = Router(name="admin.look")


async def look_doc(look: Look, looks: LookService, lang: Language) -> Doc:
    reason = await looks.blocked_reason()
    checked = await looks.checked()
    on, off = tr("look_on", lang), tr("look_off", lang)
    telegram = tr("look_blocked", lang, reason=esc(reason)) if reason else tr("look_ok", lang)
    if checked is None:
        check = tr("look_never", lang)
    else:
        at, missing = checked
        stamp = when(datetime.fromtimestamp(at, UTC), lang)
        check = tr("look_checked", lang, time=stamp, missing=num(missing, lang))
    doc = Doc().h(tr("look_title", lang), 2)
    doc.kv(
        [
            (tr("look_premium", lang), on if look.premium else off),
            (tr("look_rich", lang), on if look.rich else off),
            (tr("look_telegram", lang), telegram),
            (tr("look_check", lang), check),
        ]
    )
    doc.p(tr("look_help", lang))
    return doc


def look_keyboard(look: Look, lang: Language, buttons: ButtonOverrides, *, blocked: bool):
    premium = tr("btn_premium_on" if look.premium else "btn_premium_off", lang)
    rich = tr("btn_rich_on" if look.rich else "btn_rich_off", lang)
    rows: list[list[tuple[str, str] | tuple[str, str, str | None]]] = [
        [(premium, cb.ADMIN_LOOK_PREMIUM), (rich, cb.ADMIN_LOOK_RICH)],
        [(tr("btn_test", lang), cb.ADMIN_LOOK_TEST, "primary")],
    ]
    if blocked:
        rows.append([(tr("btn_retry", lang), cb.ADMIN_LOOK_RETRY)])
    return keyboard(lang, rows, buttons, back=cb.ADMIN_MENU)


async def show_look(
    console: Console, looks: LookService, user: User, buttons: ButtonOverrides, *, at: object
) -> None:
    look = await looks.snapshot()
    console.look = look  # a switch flipped in this update draws this screen with its new value
    lang = user.language
    blocked = await looks.blocked_reason() is not None
    markup = look_keyboard(look, lang, buttons, blocked=blocked)
    await console.show(await look_doc(look, looks, lang), markup, at=at)


@router.callback_query(F.data == cb.ADMIN_LOOK)
async def admin_look(
    callback: CallbackQuery,
    user: User,
    looks: LookService,
    console: Console,
    buttons: ButtonOverrides,
) -> None:
    await callback.answer()
    await show_look(console, looks, user, buttons, at=callback.message)


@router.callback_query(F.data.in_({cb.ADMIN_LOOK_PREMIUM, cb.ADMIN_LOOK_RICH}))
async def toggle(
    callback: CallbackQuery,
    user: User,
    looks: LookService,
    console: Console,
    buttons: ButtonOverrides,
) -> None:
    look = console.look
    if callback.data == cb.ADMIN_LOOK_PREMIUM:
        await looks.set_switch(SettingKey.LOOK_PREMIUM, not look.premium)
    else:
        await looks.set_switch(SettingKey.LOOK_RICH, not look.rich)
    await callback.answer(tr("saved", user.language))
    await show_look(console, looks, user, buttons, at=callback.message)


@router.callback_query(F.data == cb.ADMIN_LOOK_RETRY)
async def retry_premium(
    callback: CallbackQuery,
    user: User,
    looks: LookService,
    console: Console,
    buttons: ButtonOverrides,
) -> None:
    await looks.retry()
    await callback.answer(tr("saved", user.language))
    await show_look(console, looks, user, buttons, at=callback.message)


def _sample_doc(lang: Language) -> Doc:
    """A rich message with what the console's screens are made of: a table, a folding section, a
    check list and a copy button."""
    doc = Doc().h(tr("test_table", lang), 2)
    doc.kv(
        [
            ("🖥 " + tr("stats_location", lang), "🇩🇪 Germany • 🟢"),
            ("👥 " + tr("stats_users", lang), num(1234, lang)),
        ]
    )
    doc.details(tr("test_details", lang), Doc().checks([(True, "✅ A"), (False, "B")]))
    doc.row([Btn(tr("copy", lang), copy="203.0.113.7")], align="left")
    return doc


@router.callback_query(F.data == cb.ADMIN_LOOK_TEST)
async def self_test(
    callback: CallbackQuery,
    user: User,
    state: FSMContext,
    console: Console,
    buttons: ButtonOverrides,
) -> None:
    """Samples go out as NEW messages under the screen; the question becomes the screen, and its
    answer removes the samples again."""
    await callback.answer()
    lang = user.language
    colours = keyboard(
        lang,
        [
            [
                ("✅ " + tr("sample_green", lang), cb.ADMIN_LOOK_SAMPLE, "success"),
                ("🔄 " + tr("sample_blue", lang), cb.ADMIN_LOOK_SAMPLE, "primary"),
                ("🗑 " + tr("sample_red", lang), cb.ADMIN_LOOK_SAMPLE, "danger"),
            ]
        ],
        buttons,
    )
    sent = [
        await console.send(tr("test_sample", lang), colours),
        await console.send(_sample_doc(lang)),
    ]
    await state.update_data(look_samples=[m.message_id for m in sent])
    answer = keyboard(
        lang,
        [
            [
                (tr("btn_test_yes", lang), cb.ADMIN_LOOK_TEST_YES, "success"),
                (tr("btn_test_no", lang), cb.ADMIN_LOOK_TEST_NO, "danger"),
            ]
        ],
        buttons,
    )
    await console.show(tr("test_question", lang), answer, new=True)


@router.callback_query(F.data == cb.ADMIN_LOOK_SAMPLE)
async def sample_tap(callback: CallbackQuery, user: User) -> None:
    await callback.answer(tr("sample_tap", user.language))


@router.callback_query(F.data.in_({cb.ADMIN_LOOK_TEST_YES, cb.ADMIN_LOOK_TEST_NO}))
async def self_test_answer(
    callback: CallbackQuery,
    user: User,
    state: FSMContext,
    looks: LookService,
    console: Console,
    buttons: ButtonOverrides,
) -> None:
    await callback.answer()
    data = await state.get_data()
    for message_id in data.get("look_samples") or []:
        with contextlib.suppress(Exception):
            await console.bot.delete_message(console.chat_id, int(message_id))
    await state.update_data(look_samples=None)
    if callback.data == cb.ADMIN_LOOK_TEST_NO:
        await looks.set_switch(SettingKey.LOOK_PREMIUM, False)
        await looks.set_switch(SettingKey.LOOK_RICH, False)
    await show_look(console, looks, user, buttons, at=callback.message)


@router.message(Command("simple"))
async def simple(
    message: Message,
    user: User,
    state: FSMContext,
    looks: LookService,
    console: Console,
) -> None:
    """Both switches off, answered with a plain regular message (see the module docstring)."""
    await state.clear()
    await looks.set_switch(SettingKey.LOOK_PREMIUM, False)
    await looks.set_switch(SettingKey.LOOK_RICH, False)
    await console.consume(message)
    console.look = PLAIN
    await console.show(tr("simple_done", user.language), new=True)  # the old screen goes with it
