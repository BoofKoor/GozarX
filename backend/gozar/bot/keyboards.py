"""Inline keyboards.

Each builder declares its layout as a ``list[list[ButtonSpec]]`` and delegates to
``render_rows`` (gozar.ui.buttons), which applies the admin's DB overrides (label / visibility /
order) carried by the per-update ``ButtonOverrides`` snapshot. With ``buttons=None`` the output is
identical to the original hand-written ``.adjust(...)`` layouts. Data-driven cells (location
remarks, language names) are passed as raw (keyless) specs — rendered verbatim, never overridden.
"""

from __future__ import annotations

from urllib.parse import quote

from aiogram.types import InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from gozar.bot import callbacks as cb
from gozar.db.models.enums import Language
from gozar.ui.buttons import ButtonOverrides, ButtonSpec, render_rows
from gozar.ui.labels import LANGUAGE_NAMES

# Locations per picker page; longer squads paginate with Next/Prev (v1's after_before_keyboard).
_PAGE_SIZE = 8


def language_keyboard() -> InlineKeyboardMarkup:
    # The language picker runs before a language is chosen and carries only the (non-overridable)
    # language names, so it builds raw buttons directly rather than through the override renderer.
    builder = InlineKeyboardBuilder()
    for lang in (Language.fa, Language.en, Language.ru):
        builder.button(text=LANGUAGE_NAMES[lang], callback_data=cb.lang_cb(lang.value))
    builder.adjust(1)
    return builder.as_markup()


def main_menu_keyboard(
    lang: Language, buttons: ButtonOverrides | None = None
) -> InlineKeyboardMarkup:
    structure = [
        [ButtonSpec(key="menu_config", callback_data=cb.MENU_CONFIG)],
        [
            ButtonSpec(key="menu_invite", callback_data=cb.MENU_INVITE),
            ButtonSpec(key="menu_status", callback_data=cb.MENU_STATUS),
        ],
        [
            ButtonSpec(key="menu_help", callback_data=cb.MENU_HELP),
            ButtonSpec(key="menu_settings", callback_data=cb.MENU_SETTINGS),
        ],
    ]
    return render_rows(lang, structure, buttons)


def back_keyboard(lang: Language, buttons: ButtonOverrides | None = None) -> InlineKeyboardMarkup:
    return render_rows(lang, [[ButtonSpec(key="back", callback_data=cb.MENU_HOME)]], buttons)


def help_keyboard(lang: Language, buttons: ButtonOverrides | None = None) -> InlineKeyboardMarkup:
    """Help screen — carries the required-apps shortcut (v1 attaches it here, not to the picker)."""
    structure = [
        [ButtonSpec(key="apps", callback_data=cb.MENU_APPS)],
        [ButtonSpec(key="back", callback_data=cb.MENU_HOME)],
    ]
    return render_rows(lang, structure, buttons)


def landing_keyboard(
    lang: Language, *, active: bool, buttons: ButtonOverrides | None = None
) -> InlineKeyboardMarkup:
    """Get-config landing (v1). Claimable -> a get-config button that provisions on tap; active ->
    a change-location button. Both carry the 🔋 free-traffic referral shortcut + back."""
    first = (
        ButtonSpec(key="change_location", callback_data=cb.CONFIG_CHANGE)
        if active
        else ButtonSpec(key="get_config", callback_data=cb.CONFIG_CLAIM)
    )
    structure = [
        [first],
        [ButtonSpec(key="increase_traffic", callback_data=cb.MENU_INVITE)],
        [ButtonSpec(key="back", callback_data=cb.MENU_HOME)],
    ]
    return render_rows(lang, structure, buttons)


def location_keyboard(
    remarks: list[str],
    prefix: str,
    lang: Language,
    *,
    page: int = 0,
    buttons: ButtonOverrides | None = None,
) -> InlineKeyboardMarkup:
    """Paginated picker over location remark NAMES.

    Each button is keyed by its **global** index, and the chosen name resolves to its link by NAME
    (never a cross-index between two lists). ``page`` is a pure view offset into the same cached
    remarks. The location buttons are raw (data-driven) cells; only the Prev/Next nav (shown when
    there's more than one page) and the back-to-landing button are catalogue chrome.
    """
    page_count = max(1, (len(remarks) + _PAGE_SIZE - 1) // _PAGE_SIZE)
    page = min(max(page, 0), page_count - 1)
    window = range(page * _PAGE_SIZE, min((page + 1) * _PAGE_SIZE, len(remarks)))

    structure: list[list[ButtonSpec]] = [
        [ButtonSpec(label=remarks[index], callback_data=f"{prefix}{index}")] for index in window
    ]

    tag = "claim" if prefix == cb.CONFIG_CLAIM_PREFIX else "change"
    nav_row: list[ButtonSpec] = []
    if page > 0:
        nav_row.append(ButtonSpec(key="nav_prev", callback_data=cb.loc_page_cb(tag, page - 1)))
    if page < page_count - 1:
        nav_row.append(ButtonSpec(key="nav_next", callback_data=cb.loc_page_cb(tag, page + 1)))
    if nav_row:
        structure.append(nav_row)  # Prev/Next share one row

    structure.append([ButtonSpec(key="back", callback_data=cb.MENU_CONFIG)])  # back to the landing
    return render_rows(lang, structure, buttons)


def config_delivered_keyboard(
    lang: Language, buttons: ButtonOverrides | None = None
) -> InlineKeyboardMarkup:
    # "show main menu" sends a NEW message (MENU_HOME_NEW) so the delivered config stays in chat.
    structure = [
        [ButtonSpec(key="change_location", callback_data=cb.CONFIG_CHANGE)],
        [ButtonSpec(key="show_menu", callback_data=cb.MENU_HOME_NEW)],
    ]
    return render_rows(lang, structure, buttons)


def status_keyboard(
    lang: Language, *, active: bool, buttons: ButtonOverrides | None = None
) -> InlineKeyboardMarkup:
    structure: list[list[ButtonSpec]] = []
    if active:
        structure.append([ButtonSpec(key="change_location", callback_data=cb.CONFIG_CHANGE)])
    structure.append([ButtonSpec(key="back", callback_data=cb.MENU_HOME)])
    return render_rows(lang, structure, buttons)


def settings_keyboard(
    lang: Language, buttons: ButtonOverrides | None = None
) -> InlineKeyboardMarkup:
    structure = [
        [
            ButtonSpec(key="settings_language", callback_data=cb.SETTINGS_LANGUAGE),
            ButtonSpec(key="settings_reminder", callback_data=cb.SETTINGS_REMINDER),
        ],
        [ButtonSpec(key="back", callback_data=cb.MENU_HOME)],
    ]
    return render_rows(lang, structure, buttons)


def reminder_keyboard(
    lang: Language, *, reminder_enabled: bool, buttons: ButtonOverrides | None = None
) -> InlineKeyboardMarkup:
    """Reminder sub-screen: one state toggle (enable when off / disable when on) + back."""
    toggle = (
        ButtonSpec(key="reminder_disable", callback_data=cb.SETTINGS_REMINDER_OFF)
        if reminder_enabled
        else ButtonSpec(key="reminder_enable", callback_data=cb.SETTINGS_REMINDER_ON)
    )
    structure = [[toggle], [ButtonSpec(key="back", callback_data=cb.MENU_SETTINGS)]]
    return render_rows(lang, structure, buttons)


def invite_keyboard(
    lang: Language, link: str, buttons: ButtonOverrides | None = None
) -> InlineKeyboardMarkup:
    structure: list[list[ButtonSpec]] = []
    if link.startswith("http"):  # a real deep link (bot_username configured) — offer one-tap share
        structure.append(
            [ButtonSpec(key="invite_share", url=f"https://t.me/share/url?url={quote(link)}")]
        )
    structure.append([ButtonSpec(key="back", callback_data=cb.MENU_HOME)])
    return render_rows(lang, structure, buttons)


# --- Admin panel (owner-only) keyboards ---------------------------------------------------------
def admin_menu_keyboard(
    lang: Language, buttons: ButtonOverrides | None = None
) -> InlineKeyboardMarkup:
    structure = [
        [
            ButtonSpec(key="admin_stats", callback_data=cb.ADMIN_STATS),
            ButtonSpec(key="admin_users", callback_data=cb.ADMIN_USERS),
        ],
        [
            ButtonSpec(key="admin_broadcast", callback_data=cb.ADMIN_BROADCAST),
            ButtonSpec(key="admin_forward", callback_data=cb.ADMIN_FORWARD),
        ],
        [
            ButtonSpec(key="admin_refresh_locations", callback_data=cb.ADMIN_REFRESH_LOCATIONS),
            ButtonSpec(key="admin_reset_all", callback_data=cb.ADMIN_RESET_ALL),
        ],
        [ButtonSpec(key="admin_close", callback_data=cb.ADMIN_CLOSE)],
    ]
    return render_rows(lang, structure, buttons)


def admin_back_keyboard(
    lang: Language, buttons: ButtonOverrides | None = None
) -> InlineKeyboardMarkup:
    return render_rows(lang, [[ButtonSpec(key="admin_back", callback_data=cb.ADMIN_MENU)]], buttons)


def confirm_keyboard(
    lang: Language,
    confirm_cb: str,
    cancel_cb: str,
    *,
    confirm_key: str = "admin_confirm",
    buttons: ButtonOverrides | None = None,
) -> InlineKeyboardMarkup:
    """Generic ✅/❌ gate — the broadcast/forward preview, the per-user destructive confirm, and the
    bulk reset confirm all reuse it (only the confirm/cancel callbacks differ; ``confirm_key`` picks
    the "Send" vs "Confirm" label)."""
    structure = [
        [
            ButtonSpec(key=confirm_key, callback_data=confirm_cb),
            ButtonSpec(key="admin_cancel", callback_data=cancel_cb),
        ]
    ]
    return render_rows(lang, structure, buttons)


def admin_user_card_keyboard(
    lang: Language, *, banned: bool, buttons: ButtonOverrides | None = None
) -> InlineKeyboardMarkup:
    """Per-user actions. Ban (when active) / unban (when banned), plus reclaim + zero-referrals;
    the target telegram_id is held in FSM state, so no id is embedded in the callbacks."""
    toggle = (
        ButtonSpec(key="admin_unban", callback_data=cb.ADMIN_USER_UNBAN)
        if banned
        else ButtonSpec(key="admin_ban", callback_data=cb.ADMIN_USER_BAN)
    )
    structure = [
        [toggle],
        [
            ButtonSpec(key="admin_reclaim", callback_data=cb.ADMIN_USER_RECLAIM),
            ButtonSpec(key="admin_zero_referrals", callback_data=cb.ADMIN_USER_ZERO_REFERRALS),
        ],
        [ButtonSpec(key="admin_back", callback_data=cb.ADMIN_MENU)],
    ]
    return render_rows(lang, structure, buttons)
