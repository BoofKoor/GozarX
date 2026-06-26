"""Namespaced callback data — matched by exact prefix, never unanchored substring regex."""

from __future__ import annotations

MENU_HOME = "menu:home"
MENU_CONFIG = "menu:config"
MENU_INVITE = "menu:invite"
MENU_STATUS = "menu:status"
MENU_HELP = "menu:help"
MENU_SETTINGS = "menu:settings"

LANG_PREFIX = "lang:set:"


def lang_cb(code: str) -> str:
    return f"{LANG_PREFIX}{code}"
