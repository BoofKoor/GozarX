"""Thin async Remnawave panel client.

Every endpoint is ``# VERIFY:``-marked — paths/fields are from the official backend contracts but
the panel version may drift, so confirm against the live ``{PANEL_BASE_URL}/api`` first. Parsing is
defensive (unwrap ``{"response": ...}``, tolerate missing fields). Each call is a single bounded
attempt: on failure we log (never the token/payload) and raise ``RemnawaveError`` — no retry loops.
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any

import httpx
from pydantic import SecretStr, ValidationError

from gozar.remnawave.errors import RemnawaveError
from gozar.remnawave.links import parse_remark
from gozar.remnawave.schemas import Host, InternalSquad, PanelUser, Subscription, SystemStats

logger = logging.getLogger("gozar.remnawave")


def _unique(items: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for item in items:
        if item and item not in seen:
            seen.add(item)
            out.append(item)
    return out


def _links_from_list(links: list[str]) -> dict[str, str]:
    """remark -> link, parsed from a list of raw config-link strings (first wins per remark)."""
    out: dict[str, str] = {}
    for link in links:
        remark = parse_remark(link)
        if remark and remark not in out:
            out[remark] = link
    return out


def _parse_raw_links(raw: Any) -> dict[str, str]:
    # VERIFY: the raw subscription shape varies by panel version — a list of link strings, a
    #         {remark: link} map, or a wrapper like {"links": [...]}/{"subscription": [...]}.
    if isinstance(raw, list):
        return _links_from_list([str(x) for x in raw])
    if isinstance(raw, dict):
        for key in ("links", "subscription", "configs"):
            if isinstance(raw.get(key), list):
                return _links_from_list([str(x) for x in raw[key]])
        if raw and all(isinstance(v, str) for v in raw.values()):
            return {str(k): str(v) for k, v in raw.items()}
    return {}


class RemnawaveClient:
    def __init__(self, http: httpx.AsyncClient, base_url: str, token: SecretStr | str) -> None:
        self._http = http
        self._base = base_url.rstrip("/")
        self._token = token.get_secret_value() if isinstance(token, SecretStr) else token

    async def _request(self, method: str, path: str, *, json: Any | None = None) -> Any:
        url = f"{self._base}/api{path}"
        headers = {"Authorization": f"Bearer {self._token}"}
        try:
            resp = await self._http.request(method, url, headers=headers, json=json)
            resp.raise_for_status()
        except httpx.HTTPStatusError as exc:
            logger.warning("panel %s %s -> HTTP %s", method, path, exc.response.status_code)
            raise RemnawaveError(
                f"panel {method} {path} failed", status_code=exc.response.status_code
            ) from exc
        except httpx.HTTPError as exc:
            logger.warning("panel %s %s -> %s", method, path, type(exc).__name__)
            raise RemnawaveError(f"panel {method} {path} failed") from exc

        if resp.status_code == 204 or not resp.content:
            return {}
        data = resp.json()
        # Responses are wrapped as {"response": ...}; fall back to the raw body if absent.
        return data.get("response", data) if isinstance(data, dict) else data

    # VERIFY: POST /api/users (create-user.command.ts) — username, expireAt, trafficLimitBytes,
    #         activeInternalSquads[]. trafficLimitStrategy NO_RESET so each claim is a fresh 24h
    #         user (we never reset traffic in place); status ACTIVE so the config works at once.
    async def create_trial_user(
        self, username: str, traffic_bytes: int, expire_at: datetime, squad_uuids: list[str]
    ) -> PanelUser:
        payload = {
            "username": username,
            "expireAt": expire_at.isoformat(),
            "trafficLimitBytes": traffic_bytes,
            "trafficLimitStrategy": "NO_RESET",
            "status": "ACTIVE",
            "activeInternalSquads": squad_uuids,
        }
        return PanelUser.model_validate(await self._request("POST", "/users", json=payload))

    # VERIFY: GET /api/users/by-username/{username}
    async def get_user(self, username: str) -> PanelUser | None:
        try:
            data = await self._request("GET", f"/users/by-username/{username}")
        except RemnawaveError as exc:
            if exc.status_code == 404:
                return None
            raise
        return PanelUser.model_validate(data)

    # VERIFY: PATCH /api/users (update-user.command.ts) keys off the user UUID, not username — so
    #         the referral bump (Phase 5) fetches the user by username for its uuid, then PATCHes.
    async def update_traffic_limit(self, uuid: str, traffic_bytes: int) -> PanelUser:
        payload = {"uuid": uuid, "trafficLimitBytes": traffic_bytes}
        return PanelUser.model_validate(await self._request("PATCH", "/users", json=payload))

    # VERIFY: DELETE /api/users/{uuid} -> response.isDeleted
    async def delete_user(self, uuid: str) -> bool:
        data = await self._request("DELETE", f"/users/{uuid}")
        return bool(data.get("isDeleted", True)) if isinstance(data, dict) else True

    # VERIFY: POST /api/users/{uuid}/actions/reset-traffic -> response.isReset. Zeroes the user's
    #         used traffic for the current period (admin bulk "reset daily consumption"). Single
    #         bounded attempt per user; the caller logs + skips on failure (no retry loop).
    async def reset_user_traffic(self, uuid: str) -> bool:
        data = await self._request("POST", f"/users/{uuid}/actions/reset-traffic")
        return bool(data.get("isReset", True)) if isinstance(data, dict) else True

    # VERIFY: GET /api/system/stats -> response.{onlineStats,users,nodes,cpu,memory,…}. Confirmed
    #         against @remnawave/backend-contract: onlineStats.onlineNow is the LIVE online-users
    #         count (panel-wide), with lastDay/lastWeek/neverOnline, users.statusCounts/totalUsers,
    #         and nodes.totalOnline/totalBytesLifetime (a string). Single bounded attempt; returns
    #         None on error/odd shape so the dashboard falls back to the DB active count.
    async def system_stats(self) -> SystemStats | None:
        try:
            data = await self._request("GET", "/system/stats")
        except RemnawaveError:
            return None
        if not isinstance(data, dict):
            return None
        try:
            return SystemStats.model_validate(data)
        except ValidationError:
            logger.warning("panel /system/stats returned an unexpected shape")
            return None

    # VERIFY: GET /api/internal-squads -> response.internalSquads[]
    async def list_internal_squads(self) -> list[InternalSquad]:
        data = await self._request("GET", "/internal-squads")
        squads = data.get("internalSquads", []) if isinstance(data, dict) else []
        return [InternalSquad.model_validate(s) for s in squads]

    # VERIFY: GET /api/hosts -> list of hosts; .remark is the location name
    async def list_hosts(self) -> list[Host]:
        data = await self._request("GET", "/hosts")
        if isinstance(data, list):
            hosts = data
        elif isinstance(data, dict):
            hosts = data.get("hosts", [])
        else:
            hosts = []
        return [Host.model_validate(h) for h in hosts]

    # VERIFY: GET /api/subscriptions/by-username/{username} -> {links, ssConfLinks, user}. Carries
    #         the user's shortUuid + status/expireAt (basis for both the picker and the self-heal).
    async def get_subscription(self, username: str) -> Subscription:
        return Subscription.model_validate(
            await self._request("GET", f"/subscriptions/by-username/{username}")
        )

    # VERIFY: GET /api/subscriptions/raw/{shortUuid} — raw config data; shape is panel-version-
    #         sensitive (a link list, a {remark: link} map, or a wrapper), so we parse defensively.
    async def get_subscription_raw(self, short_uuid: str) -> Any:
        return await self._request("GET", f"/subscriptions/raw/{short_uuid}")

    async def subscription(self, username: str) -> tuple[Subscription, dict[str, str]]:
        """The user's own subscription paired with a remark NAME -> config link map.

        Single source of truth for the location picker: the picker's names and the link handed back
        on a pick both come from this one response, so they can never cross-index (the v1 bug). We
        try, in order: the by-username ``ssConfLinks`` map; else parse remarks out of ``links[]``;
        else fall back to the raw endpoint (whose shape varies). All shape handling is # VERIFY:.
        """
        sub = await self.get_subscription(username)
        links = dict(sub.ss_conf_links)
        if not links:
            links = _links_from_list(sub.links)
        if not links and sub.user.short_uuid:
            links = _parse_raw_links(await self.get_subscription_raw(sub.user.short_uuid))
        return sub, links

    async def squad_location_names(self, squad_uuid: str) -> list[str]:
        """Location remark names available to a squad.

        VERIFY: there's no direct squad->hosts endpoint, so we match the squad's inbound UUIDs to
        ``host.inbound.configProfileInboundUuid`` and drop hosts that exclude the squad. If nothing
        matches (panel drift), fall back to every enabled host's remark so the wizard has options.
        """
        squads = await self.list_internal_squads()
        hosts = await self.list_hosts()
        enabled = [h for h in hosts if not h.is_disabled]
        squad = next((s for s in squads if s.uuid == squad_uuid), None)
        if squad is None:
            return _unique([h.remark for h in enabled])

        inbound_uuids = {
            i.config_profile_inbound_uuid for i in squad.inbounds if i.config_profile_inbound_uuid
        }
        matched = [
            h.remark
            for h in enabled
            if h.inbound.config_profile_inbound_uuid in inbound_uuids
            and squad_uuid not in h.excluded_internal_squads
        ]
        return _unique(matched) or _unique([h.remark for h in enabled])
