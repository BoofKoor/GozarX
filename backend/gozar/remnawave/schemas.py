"""Pydantic models for Remnawave responses.

Deliberately tolerant: ``extra="ignore"`` + every field optional with a default, so a panel field
rename degrades gracefully (missing data) instead of raising. camelCase API keys map to snake_case
via aliases; ``populate_by_name`` lets tests build models with either name.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class _Base(BaseModel):
    model_config = ConfigDict(extra="ignore", populate_by_name=True)


class UserTraffic(_Base):
    used_bytes: int = Field(default=0, alias="usedTrafficBytes")


class PanelUser(_Base):
    uuid: str = ""
    username: str = ""
    status: str = ""  # ACTIVE | DISABLED | LIMITED | EXPIRED
    traffic_limit_bytes: int = Field(default=0, alias="trafficLimitBytes")
    expire_at: str | None = Field(default=None, alias="expireAt")
    subscription_url: str | None = Field(default=None, alias="subscriptionUrl")
    traffic: UserTraffic = Field(default_factory=UserTraffic, alias="userTraffic")


class SquadInbound(_Base):
    uuid: str = ""
    config_profile_inbound_uuid: str | None = Field(default=None, alias="configProfileInboundUuid")


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


class WebhookUserEvent(_Base):
    """Panel -> server user event (consumed by the Phase 5 /panel-webhook receiver)."""

    scope: str = ""
    event: str = ""  # e.g. user.expired | user.limited
    timestamp: str | None = None
    data: PanelUser = Field(default_factory=PanelUser)
    meta: dict | None = None
