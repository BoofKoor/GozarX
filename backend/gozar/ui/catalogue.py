"""Button catalogue — the source of truth for which **static chrome** buttons exist, which screen
each belongs to, and their default row/position (today's ``.adjust(...)`` layout).

The admin panel edits these via ``button_configs`` (label / visibility / order); the keyboards
render them through ``render_rows``. Data-driven buttons (location list, language picker) are NOT
in the catalogue — they render as raw, non-overridable cells.

A key may appear on several screens (shared chrome like ``back``); the override is keyed by the
i18n key, so a label rename applies everywhere. ``CRITICAL_KEYS`` can't be hidden and stay pinned
to their structural slot (so a global override can't strand them on a screen).
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

# Navigation escapes + confirm/cancel gates: never hideable, never reordered.
CRITICAL_KEYS: frozenset[str] = frozenset(
    {
        "back",
        "admin_back",
        "show_menu",
        "admin_close",
        "admin_confirm",
        "admin_cancel",
        "admin_send",
        "nav_prev",
        "nav_next",
    }
)


class Screen(StrEnum):
    main_menu = "main_menu"
    landing = "landing"
    help = "help"
    config_delivered = "config_delivered"
    status = "status"
    settings = "settings"
    invite = "invite"
    location = "location"
    admin_menu = "admin_menu"
    admin_user_card = "admin_user_card"
    confirm = "confirm"
    admin_back = "admin_back"


@dataclass(frozen=True, slots=True)
class CatalogueEntry:
    key: str
    screen: Screen
    default_row: int
    default_position: int

    @property
    def is_critical(self) -> bool:
        return self.key in CRITICAL_KEYS


def _entries(screen: Screen, specs: list[tuple[str, int, int]]) -> list[CatalogueEntry]:
    """Expand ``(key, row, position)`` triples into entries (alternatives may share a cell)."""
    return [CatalogueEntry(key, screen, row, pos) for key, row, pos in specs]


# Each screen mirrors the matching builder in ``bot/keyboards.py`` (row/position = today's layout).
# Conditional alternatives (get_config|change_location, reminder_on|off, ban|unban, confirm|send)
# share one cell — the builder renders whichever the runtime state selects.
CATALOGUE: tuple[CatalogueEntry, ...] = tuple(
    _entries(
        Screen.main_menu,
        [
            ("menu_config", 0, 0),
            ("menu_invite", 1, 0),
            ("menu_status", 1, 1),
            ("menu_help", 2, 0),
            ("menu_settings", 2, 1),
        ],
    )
    + _entries(
        Screen.landing,
        [
            ("get_config", 0, 0),
            ("change_location", 0, 0),
            ("increase_traffic", 1, 0),
            ("back", 2, 0),
        ],
    )
    + _entries(Screen.help, [("apps", 0, 0), ("back", 1, 0)])
    + _entries(Screen.config_delivered, [("change_location", 0, 0), ("show_menu", 1, 0)])
    + _entries(Screen.status, [("change_location", 0, 0), ("back", 1, 0)])
    + _entries(
        Screen.settings,
        [
            ("settings_language", 0, 0),
            ("reminder_on", 0, 1),  # reminder_on|reminder_off share the toggle cell
            ("reminder_off", 0, 1),
            ("back", 1, 0),
        ],
    )
    + _entries(Screen.invite, [("invite_share", 0, 0), ("back", 1, 0)])
    + _entries(Screen.location, [("nav_prev", 0, 0), ("nav_next", 0, 1), ("back", 1, 0)])
    + _entries(
        Screen.admin_menu,
        [
            ("admin_stats", 0, 0),
            ("admin_users", 0, 1),
            ("admin_broadcast", 1, 0),
            ("admin_forward", 1, 1),
            ("admin_refresh_locations", 2, 0),
            ("admin_reset_all", 2, 1),
            ("admin_close", 3, 0),
        ],
    )
    + _entries(
        Screen.admin_user_card,
        [
            ("admin_ban", 0, 0),
            ("admin_unban", 0, 0),
            ("admin_reclaim", 1, 0),
            ("admin_zero_referrals", 1, 1),
            ("admin_back", 2, 0),
        ],
    )
    + _entries(
        Screen.confirm,
        [("admin_confirm", 0, 0), ("admin_send", 0, 0), ("admin_cancel", 0, 1)],
    )
    + _entries(Screen.admin_back, [("admin_back", 0, 0)])
)
