"""📊 Stats: the totals, today, the last seven local days, today's locations, the top inviters.

Everything is from the DB on the operator's calendar (Asia/Tehran). A capped list says what it hid
("and N more"), and a section with nothing to show is left out rather than drawn empty.
"""

from __future__ import annotations

from datetime import date

from aiogram import F, Router
from aiogram.types import CallbackQuery

from gozar.bot import callbacks as cb
from gozar.bot.handlers.admin.console import Console
from gozar.bot.keyboards import admin_back_keyboard
from gozar.db.models.enums import Language
from gozar.db.models.user import User
from gozar.services.admin import AdminService, ConsoleStats
from gozar.ui.buttons import ButtonOverrides
from gozar.ui.console_text import tr
from gozar.ui.flags import with_flag
from gozar.ui.fmt import digits, num
from gozar.ui.rich import Doc, copy, esc

router = Router(name="admin.stats")


def _day(day: str, lang: Language) -> str:
    """'2026-10-19' -> '10-19' in the reader's digits (the week table only needs month-day)."""
    try:
        parsed = date.fromisoformat(day)
    except ValueError:
        return day
    return digits(parsed.strftime("%m-%d"), lang)


def stats_doc(s: ConsoleStats, lang: Language) -> Doc:
    t = s.totals
    doc = Doc().h(tr("stats_title", lang), 2)
    doc.kv(
        [
            (tr("stats_total", lang), num(t.total, lang)),
            (tr("stats_available", lang), num(t.available, lang)),
            (tr("stats_active", lang), num(t.active, lang)),
            (tr("stats_banned", lang), num(t.banned, lang)),
            (tr("stats_referrals", lang), num(t.referrals, lang)),
        ],
        caption=tr("stats_users", lang),
    )
    doc.kv(
        [
            (tr("stats_claims", lang), num(t.configs_today, lang)),
            (tr("stats_new", lang), num(s.new_today, lang)),
            (tr("stats_active_users", lang), num(s.active_users_today, lang)),
        ],
        caption=tr("stats_today", lang),
    )
    doc.table(
        [tr("stats_day", lang), tr("stats_claims", lang), tr("stats_signups", lang)],
        [
            [_day(day, lang), num(claims, lang), num(signups, lang)]
            for day, claims, signups in s.week
        ],
        striped=True,
        caption=tr("stats_week", lang),
    )
    if s.locations:
        rows = [[esc(with_flag(name)), num(n, lang)] for name, n in s.locations]
        hidden = s.locations_total - len(s.locations)
        if hidden > 0:
            rows.append([tr("stats_more", lang, n=num(hidden, lang)), ""])
        doc.table(
            [tr("stats_location", lang), tr("stats_claims", lang)],
            rows,
            caption=tr("stats_locations", lang),
        )
    if s.top_referrers:
        doc.table(
            [tr("stats_user", lang), tr("stats_invites", lang)],
            [
                [f"<code>{uid}</code> {copy(str(uid), tr('copy', lang))}", num(n, lang)]
                for uid, n in s.top_referrers
            ],
            caption=tr("stats_top", lang),
        )
    return doc


@router.callback_query(F.data == cb.ADMIN_STATS)
async def admin_stats(
    callback: CallbackQuery,
    user: User,
    admin: AdminService,
    console: Console,
    buttons: ButtonOverrides,
) -> None:
    await callback.answer()
    doc = stats_doc(await admin.console_stats(), user.language)
    await console.show(doc, admin_back_keyboard(user.language, buttons), at=callback.message)
