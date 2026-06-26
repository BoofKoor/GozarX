"""Namespaced callback data — matched by exact prefix, never unanchored substring regex."""

from __future__ import annotations

MENU_HOME = "menu:home"
MENU_CONFIG = "menu:config"
MENU_INVITE = "menu:invite"
MENU_STATUS = "menu:status"
MENU_HELP = "menu:help"
MENU_SETTINGS = "menu:settings"
MENU_APPS = "menu:apps"  # required-apps info screen

LANG_PREFIX = "lang:set:"

# Config flow. CLAIM is the first delivery for a chosen location (writes one config_log); LOC is a
# change-location delivery (no log); CHANGE re-opens the picker. Index addresses the cached picker.
CONFIG_CLAIM_PREFIX = "config:claim:"
CONFIG_LOC_PREFIX = "config:loc:"
CONFIG_CHANGE = "config:change"

# Location-picker pagination: loc:page:{tag}:{N}. The tag ("claim" | "loc") preserves which delivery
# prefix the re-rendered page uses, so a paginated first-claim picker still logs via config:claim:.
LOC_PAGE_PREFIX = "loc:page:"

# Settings screen.
SETTINGS_LANG = "settings:lang"
SETTINGS_REMINDER_TOGGLE = "settings:reminder"


def lang_cb(code: str) -> str:
    return f"{LANG_PREFIX}{code}"


def config_claim_cb(index: int) -> str:
    return f"{CONFIG_CLAIM_PREFIX}{index}"


def config_loc_cb(index: int) -> str:
    return f"{CONFIG_LOC_PREFIX}{index}"


def loc_page_cb(tag: str, page: int) -> str:
    return f"{LOC_PAGE_PREFIX}{tag}:{page}"
