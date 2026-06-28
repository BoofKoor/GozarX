"""Namespaced callback data — matched by exact prefix, never unanchored substring regex."""

from __future__ import annotations

MENU_HOME = "menu:home"
MENU_HOME_NEW = "menu:home:new"  # deliver screen's "show main menu" -> sends a NEW message
MENU_CONFIG = "menu:config"
MENU_INVITE = "menu:invite"
MENU_STATUS = "menu:status"
MENU_HELP = "menu:help"
MENU_SETTINGS = "menu:settings"
MENU_APPS = "menu:apps"  # required-apps info screen

LANG_PREFIX = "lang:set:"

# Config flow. menu:config -> landing; CONFIG_CLAIM (exact) is the landing's inner get-config button
# that provisions; CONFIG_CHANGE (exact) opens the change picker. The {i}-suffixed prefixes are the
# per-location deliveries: CLAIM writes one config_log (first claim); CHANGE re-delivers, no log.
# (`config:claim` does not start with `config:claim:`, so exact and prefix never collide.)
CONFIG_CLAIM = "config:claim"
CONFIG_CLAIM_PREFIX = "config:claim:"
CONFIG_CHANGE = "config:change"
CONFIG_CHANGE_PREFIX = "config:change:"

# Location-picker pagination: loc:page:{tag}:{N}. The tag ("claim" | "change") preserves which
# delivery prefix the re-rendered page uses, so a paginated first claim still logs via claim path.
LOC_PAGE_PREFIX = "loc:page:"

# Settings screen. The reminder is a single stateful toggle right on the settings keyboard (no
# sub-screen): one tap flips reminder_enabled and pops a toast.
SETTINGS_LANGUAGE = "settings:language"
SETTINGS_REMINDER_TOGGLE = "settings:reminder:toggle"

# Admin panel (owner-only; the IsOwner filter gates the whole router). All exact-match. Per-user
# actions carry NO id — the target telegram_id lives in the UserActionFlow FSM state, so the card
# buttons stay stateless. The preview gate (SEND_CONFIRM/CANCEL) is what releases a broadcast.
ADMIN_MENU = "admin:menu"
ADMIN_STATS = "admin:stats"
ADMIN_BROADCAST = "admin:broadcast"
ADMIN_FORWARD = "admin:forward"
ADMIN_USERS = "admin:users"
ADMIN_REFRESH_LOCATIONS = "admin:refresh_locations"
ADMIN_RESET_ALL = "admin:reset_all"
ADMIN_RESET_ALL_CONFIRM = "admin:reset_all:confirm"  # exact; != "admin:reset_all"
ADMIN_CLOSE = "admin:close"
ADMIN_SEND_CONFIRM = "admin:send:confirm"
ADMIN_SEND_CANCEL = "admin:send:cancel"
ADMIN_USER_BAN = "admin:user:ban"
ADMIN_USER_UNBAN = "admin:user:unban"
ADMIN_USER_RECLAIM = "admin:user:reclaim"
ADMIN_USER_ZERO_REFERRALS = "admin:user:zero_referrals"
ADMIN_USER_CONFIRM = "admin:user:confirm"
ADMIN_USER_CANCEL = "admin:user:cancel"


def lang_cb(code: str) -> str:
    return f"{LANG_PREFIX}{code}"


def config_claim_cb(index: int) -> str:
    return f"{CONFIG_CLAIM_PREFIX}{index}"


def config_change_cb(index: int) -> str:
    return f"{CONFIG_CHANGE_PREFIX}{index}"


def loc_page_cb(tag: str, page: int) -> str:
    return f"{LOC_PAGE_PREFIX}{tag}:{page}"
