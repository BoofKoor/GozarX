"""📍 The users' locations: what the trial squad serves, what the picker offers, today's claims.

Read from the panel when opened (one bounded pair of reads). 🔄 stores ``[]`` — "every location the
squad serves" — so a host added later appears by itself (``AdminService.refresh_locations``).
"""

from __future__ import annotations

from aiogram import F, Router
from aiogram.types import CallbackQuery

from gozar.bot import callbacks as cb
from gozar.bot.handlers.admin.console import Console, keyboard
from gozar.db.models.enums import Language
from gozar.db.models.user import User
from gozar.services.admin import AdminService, LocationOverview
from gozar.services.content import ContentService
from gozar.ui.buttons import ButtonOverrides
from gozar.ui.console_text import tr
from gozar.ui.flags import with_flag
from gozar.ui.fmt import num
from gozar.ui.rich import Doc, esc

router = Router(name="admin.locations")


def locations_doc(o: LocationOverview, lang: Language, note: str | None = None) -> Doc:
    doc = Doc()
    if note:
        doc.quote(note)
    doc.h(tr("loc_title", lang), 2)
    if not o.squad_uuid:
        return doc.p(tr("loc_no_squad", lang))
    doc.kv([(tr("loc_squad", lang), esc(o.squad_name) or f"<code>{esc(o.squad_uuid)}</code>")])
    if o.names is None:
        return doc.p(tr("loc_panel_error", lang))
    if not o.names:
        return doc.p(tr("loc_none", lang))
    doc.p(tr("loc_count", lang, n=num(len(o.offered), lang)))
    doc.table(
        [tr("loc_name", lang), tr("loc_today", lang)],
        [[esc(with_flag(name)), num(o.today.get(name, 0), lang)] for name in o.offered],
        striped=True,
    )
    if o.allow and len(o.offered) < len(o.names):
        doc.footer(
            tr("loc_subset_note", lang, n=num(len(o.offered), lang), total=num(len(o.names), lang))
        )
    else:
        doc.footer(tr("loc_all_note", lang))
    return doc


def locations_keyboard(lang: Language, buttons: ButtonOverrides, *, refresh: bool):
    rows = [[(tr("btn_refresh", lang), cb.ADMIN_REFRESH_LOCATIONS, "primary")]] if refresh else []
    return keyboard(lang, rows, buttons, back=cb.ADMIN_MENU)


@router.callback_query(F.data == cb.ADMIN_LOCATIONS)
async def admin_locations(
    callback: CallbackQuery,
    user: User,
    admin: AdminService,
    console: Console,
    buttons: ButtonOverrides,
) -> None:
    await callback.answer()
    o = await admin.location_overview()
    lang = user.language
    # 🔄 only means something when a subset is stored: "all" already is what it would store
    refresh = bool(o.allow) and bool(o.names)
    markup = locations_keyboard(lang, buttons, refresh=refresh)
    await console.show(locations_doc(o, lang), markup, at=callback.message)


@router.callback_query(F.data == cb.ADMIN_REFRESH_LOCATIONS)
async def admin_refresh_locations(
    callback: CallbackQuery,
    user: User,
    content: ContentService,
    admin: AdminService,
    console: Console,
    buttons: ButtonOverrides,
) -> None:
    await callback.answer()
    lang = user.language
    names = await admin.refresh_locations()
    if names is None:
        note = await content.text("admin_refresh_failed", lang)
    else:
        note = await content.text(
            "admin_refresh_done", lang, count=len(names), locations=esc(", ".join(names) or "—")
        )
    o = await admin.location_overview()
    markup = locations_keyboard(lang, buttons, refresh=bool(o.allow) and bool(o.names))
    await console.show(locations_doc(o, lang, note), markup, at=callback.message)
