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
# 📍 the users' locations (the home's 📍 opens it; its 🔄 offers every location of the squad again).
ADMIN_LOCATIONS = "admin:locations"
# 🎨 appearance: the two switches, the self-test (and its answer), "try premium again".
ADMIN_LOOK = "admin:look"
ADMIN_LOOK_PREMIUM = "admin:look:premium"
ADMIN_LOOK_RICH = "admin:look:rich"
ADMIN_LOOK_RETRY = "admin:look:retry"
ADMIN_LOOK_TEST = "admin:look:test"
ADMIN_LOOK_TEST_YES = "admin:look:test:yes"
ADMIN_LOOK_TEST_NO = "admin:look:test:no"
ADMIN_LOOK_SAMPLE = "admin:look:sample"  # the self-test's coloured sample buttons (a toast only)

# 🖥 nodes and 🗄 servers (Phase 30). The SSH work runs in the worker as ``ops_jobs`` rows; a button
# about one job or one server carries its id (a job id is 16 hex characters), so a screen left over
# from earlier still acts on what it showed. Every prefix below is unique: none is the start of
# another, so ``startswith`` matches exactly one handler.
OPS_NODES = "ops:nodelist"
OPS_NODES_ADD = "ops:nodeadd"
OPS_NODE_SSH = "ops:nodessh:"  # + panel node uuid: save the server behind an existing node
OPS_SERVERS = "ops:srvlist"
OPS_SERVERS_ADD = "ops:srvadd"
OPS_SERVER_OPEN = "ops:srvopen:"  # + server id
OPS_SERVER_TEST = "ops:srvtest:"
OPS_SERVER_NODE = "ops:srvnode:"  # make this saved server a node
OPS_SERVER_FORGET = "ops:srvforget:"  # asks first
OPS_SERVER_FORGET_OK = "ops:srvforgetok:"
OPS_SERVER_DROP = "ops:srvdrop:"  # forget without touching the server (it can't be reached)
OPS_SERVER_TRUST = "ops:srvtrust:"  # accept the server's new SSH host key
OPS_TOKEN = "ops:token"
OPS_CANCEL = "ops:cancel"
OPS_JOB = "ops:job:"  # + job id: draw that job's screen again
OPS_JOB_LOG = "ops:joblog:"  # the job's log, as a file
OPS_JOB_RETRY = "ops:jobretry:"  # the same job again (asks the password when it needs one)
OPS_JOB_UNDO = "ops:jobundo:"  # + install job id: reverse what it got done
OPS_DRAFT_GO = "ops:draftgo:"  # + prepare job id: install the node
OPS_DRAFT_NAME = "ops:draftname:"
OPS_DRAFT_COUNTRY = "ops:draftcc:"
OPS_DRAFT_PROFILES = "ops:draftprof:"
OPS_DRAFT_PICK = "ops:draftpick:"  # + job id + ":" + profile index
OPS_DRAFT_BACK = "ops:draftback:"  # back to the summary


def ops_cb(prefix: str, *parts: object) -> str:
    return prefix + ":".join(str(p) for p in parts)


def lang_cb(code: str) -> str:
    return f"{LANG_PREFIX}{code}"


def config_claim_cb(index: int) -> str:
    return f"{CONFIG_CLAIM_PREFIX}{index}"


def config_change_cb(index: int) -> str:
    return f"{CONFIG_CHANGE_PREFIX}{index}"


def loc_page_cb(tag: str, page: int) -> str:
    return f"{LOC_PAGE_PREFIX}{tag}:{page}"
