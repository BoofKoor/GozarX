"""Pydantic models for Remnawave responses.

Deliberately tolerant: ``extra="ignore"`` + every field optional with a default, so a panel field
rename degrades gracefully (missing data) instead of raising. camelCase API keys map to snake_case
via aliases; ``populate_by_name`` lets tests build models with either name.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, model_validator


class _Base(BaseModel):
    model_config = ConfigDict(extra="ignore", populate_by_name=True)


class UserTraffic(_Base):
    used_bytes: int = Field(default=0, alias="usedTrafficBytes")
    # VERIFY (2.8.0 contract): UserItemInfo.userTraffic.onlineAt — the user's last-seen timestamp
    # (nullable ISO). Basis for the squad-scoped "online now" count on the dashboard.
    online_at: str | None = Field(default=None, alias="onlineAt")


class ActiveSquadRef(_Base):
    """One entry of ``UserItemInfo.activeInternalSquads`` (``GET /api/users``) — the squad a user
    belongs to, keyed by ``uuid`` (``name`` is present too but we only match on the id)."""

    uuid: str = ""


class PanelUser(_Base):
    uuid: str = ""
    username: str = ""
    status: str = ""  # ACTIVE | DISABLED | LIMITED | EXPIRED
    traffic_limit_bytes: int = Field(default=0, alias="trafficLimitBytes")
    expire_at: str | None = Field(default=None, alias="expireAt")
    subscription_url: str | None = Field(default=None, alias="subscriptionUrl")
    traffic: UserTraffic = Field(default_factory=UserTraffic, alias="userTraffic")
    active_internal_squads: list[ActiveSquadRef] = Field(
        default_factory=list, alias="activeInternalSquads"
    )


class SquadInbound(_Base):
    """One Config-Profile-Inbound enabled for a squad (``GET /internal-squads`` ->
    ``internalSquads[].inbounds[]``). VERIFY (live contract): each element is a config-profile
    inbound whose OWN id is ``uuid`` — squad inbounds do NOT carry a ``configProfileInboundUuid``;
    that field lives on the HOST side (``host.inbound.configProfileInboundUuid``), pointing back at
    this ``uuid``. So a squad's inbound UUIDs are matched to hosts by ``uuid``, never by a field
    the squad inbound doesn't have."""

    uuid: str = ""


class InternalSquad(_Base):
    uuid: str = ""
    name: str = ""
    inbounds: list[SquadInbound] = Field(default_factory=list)


class HostInbound(_Base):
    config_profile_inbound_uuid: str | None = Field(default=None, alias="configProfileInboundUuid")


class Host(_Base):
    uuid: str = ""
    remark: str = ""  # human location name — match configs to locations by THIS, never by index
    is_disabled: bool = Field(default=False, alias="isDisabled")
    # VERIFY: a host hidden in the panel is excluded from subscriptions but still listed by
    # GET /api/hosts, so deriving the picker without this yields names no link ever carries.
    # Defaults False, so a panel build that omits the field behaves exactly as before.
    is_hidden: bool = Field(default=False, alias="isHidden")
    inbound: HostInbound = Field(default_factory=HostInbound)
    excluded_internal_squads: list[str] = Field(
        default_factory=list, alias="excludedInternalSquads"
    )


class SubscriptionUser(_Base):
    days_left: int = Field(default=0, alias="daysLeft")
    traffic_used_bytes: int = Field(default=0, alias="trafficUsedBytes")
    traffic_limit_bytes: int = Field(default=0, alias="trafficLimitBytes")
    expires_at: str | None = Field(default=None, alias="expiresAt")
    user_status: str = Field(default="", alias="userStatus")
    short_uuid: str = Field(default="", alias="shortUuid")


class Subscription(_Base):
    is_found: bool = Field(default=True, alias="isFound")
    links: list[str] = Field(default_factory=list)
    # keyed by host remark NAME -> config link (used to match a chosen location to its link by name)
    ss_conf_links: dict[str, str] = Field(default_factory=dict, alias="ssConfLinks")
    subscription_url: str | None = Field(default=None, alias="subscriptionUrl")
    user: SubscriptionUser = Field(default_factory=SubscriptionUser)


def _coerce_int(value: object) -> int:
    """Best-effort int (the panel sends ``totalBytesLifetime`` as a STRING). Non-numeric -> 0."""
    try:
        return int(float(value))  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return 0


class SystemStats(_Base):
    """Flattened ``GET /api/system/stats`` response (the fields the dashboard needs).

    The raw payload nests these under ``onlineStats`` / ``users`` / ``nodes``; the validator pulls
    them up. Direct construction (tests) with the flat field names is passed through unchanged.
    """

    online_now: int = 0
    online_last_day: int = 0
    online_last_week: int = 0
    never_online: int = 0
    status_counts: dict[str, int] = Field(default_factory=dict)
    total_users: int = 0
    nodes_online: int = 0
    total_traffic_bytes: int = 0
    # panel host resources (for the system monitoring page)
    cpu_cores: int = 0
    mem_total: int = 0
    mem_used: int = 0
    uptime_seconds: int = 0

    @model_validator(mode="before")
    @classmethod
    def _flatten(cls, data: object) -> object:
        if not isinstance(data, dict):
            return data
        if not any(k in data for k in ("onlineStats", "users", "nodes", "cpu", "memory")):
            return data  # already flat (direct construction / tests)
        online = data.get("onlineStats") or {}
        users = data.get("users") or {}
        nodes = data.get("nodes") or {}
        cpu = data.get("cpu") or {}
        memory = data.get("memory") or {}
        return {
            "online_now": online.get("onlineNow", 0),
            "online_last_day": online.get("lastDay", 0),
            "online_last_week": online.get("lastWeek", 0),
            "never_online": online.get("neverOnline", 0),
            "status_counts": users.get("statusCounts") or {},
            "total_users": users.get("totalUsers", 0),
            "nodes_online": nodes.get("totalOnline", 0),
            "total_traffic_bytes": _coerce_int(nodes.get("totalBytesLifetime", 0)),
            "cpu_cores": cpu.get("cores", 0),
            "mem_total": _coerce_int(memory.get("total", 0)),
            "mem_used": _coerce_int(memory.get("used", 0)),
            "uptime_seconds": _coerce_int(data.get("uptime", 0)),
        }


class WebhookUserEvent(_Base):
    """Panel -> server user event (consumed by the Phase 5 /panel-webhook receiver)."""

    scope: str = ""
    event: str = ""  # e.g. user.expired | user.limited
    timestamp: str | None = None
    data: PanelUser = Field(default_factory=PanelUser)
    meta: dict | None = None
