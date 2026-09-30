"""Thin async Remnawave panel client.

Every endpoint is ``# VERIFY:``-marked — paths/fields are from the official backend contracts but
the panel version may drift, so confirm against the live ``{PANEL_BASE_URL}/api`` first. Parsing is
defensive (unwrap ``{"response": ...}``, tolerate missing fields). Each call is a single bounded
attempt: on failure we log (never the token/payload) and raise ``RemnawaveError`` — no retry loops.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta
from typing import Any

import httpx
from pydantic import SecretStr, ValidationError

from gozar.remnawave.errors import RemnawaveError
from gozar.remnawave.links import parse_remark
from gozar.remnawave.schemas import (
    Host,
    InternalSquad,
    PanelUser,
    SquadActivity,
    Subscription,
    SystemStats,
)

logger = logging.getLogger("gozar.remnawave")


def _parse_iso(value: str | None) -> datetime | None:
    """Panel ISO timestamp -> aware UTC datetime; None on absent/garbage (never raises)."""
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)


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
        try:
            data = resp.json()
        except ValueError as exc:
            # A 2xx that isn't JSON (an HTML error/challenge page from a proxy/Cloudflare fronting
            # the panel) must still raise RemnawaveError — the docstring promises it and callers
            # rely on `except RemnawaveError`; otherwise a JSONDecodeError sails past them (a 500 on
            # /claim, an aborted reconcile sweep). Never log the body (may carry sensitive markup).
            logger.warning("panel %s %s -> non-JSON body (HTTP %s)", method, path, resp.status_code)
            raise RemnawaveError(
                f"panel {method} {path} returned non-JSON", status_code=resp.status_code
            ) from exc
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

    # VERIFY: PATCH /api/users (update-user.command.ts) keyed by USERNAME — the one key both majors
    #         accept in the body: 2.x takes uuid|username, 3.x id|username (it dropped the uuid,
    #         so a body keyed by it alone is stripped to no key at all and refused with a 400).
    #         None on 404: the account is already gone, which callers treat as "nothing to bump".
    async def update_traffic_limit(self, username: str, traffic_bytes: int) -> PanelUser | None:
        payload = {"username": username, "trafficLimitBytes": traffic_bytes}
        try:
            data = await self._request("PATCH", "/users", json=payload)
        except RemnawaveError as exc:
            if exc.status_code == 404:
                return None
            raise
        return PanelUser.model_validate(data)

    # VERIFY: DELETE /api/users/{ref} — 2.x: ref = uuid, answers {isDeleted}; 3.x: ref = numeric
    #         id, answers 204 with no body. Pass ``PanelUser.ref``, never a raw uuid/id field.
    async def delete_user(self, ref: str) -> bool:
        data = await self._request("DELETE", f"/users/{ref}")
        return bool(data.get("isDeleted", True)) if isinstance(data, dict) else True

    async def delete_user_by_username(self, username: str) -> bool:
        """Resolve a username to its path key (DELETE takes the uuid on 2.x, the id on 3.x — never
        the name) and delete that panel account. Returns False when the user is already gone (404)
        or the record carries no key; a transient failure raises ``RemnawaveError`` so callers can
        treat deletion as best-effort."""
        panel_user = await self.get_user(username)  # None on 404
        if panel_user is None or not panel_user.ref:
            return False
        return await self.delete_user(panel_user.ref)

    # VERIFY: POST /api/users/{ref}/actions/reset-traffic (ref as for delete_user) -> the user.
    #         Zeroes the user's used traffic for the current period (admin bulk "reset daily
    #         consumption"). Single bounded attempt per user; the caller logs + skips on failure.
    async def reset_user_traffic(self, ref: str) -> bool:
        data = await self._request("POST", f"/users/{ref}/actions/reset-traffic")
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

    # VERIFY: GET /api/users?size&start -> response.{users[],total}. Each user (UserItemInfo) has
    #   userTraffic.onlineAt (last-seen) + activeInternalSquads[].uuid, so we can count "online now"
    #   scoped to specific squads — /system/stats only gives PANEL-WIDE. Paged in a single bounded
    #   sweep (hard page cap; NOT a retry loop), 60s-cached by the caller. Returns None on any panel
    #   error so the caller falls back to the panel-wide count. "Online" = onlineAt within
    #   ONLINE_WINDOW_SECONDS (the panel's ~60s cadence; exact cutoff isn't readable externally).
    ONLINE_WINDOW_SECONDS = 60
    _USERS_PAGE_SIZE = 500
    _USERS_MAX_PAGES = 40  # hard ceiling (20k users) so a huge panel can't become a firehose

    async def squad_online_count(self, squad_uuids: set[str]) -> SquadActivity | None:
        """Count, among users who belong to ANY of ``squad_uuids`` (the service's trial squad(s)),
        who was online in the last minute and who in the last week — excluding the operator's own
        personal squads that pollute the panel-wide ``onlineNow``. Empty input -> zeros (nothing to
        scope to).

        The week figure rides the same sweep because the dashboard gauges one against the other:
        against the panel-wide ``onlineLastWeek`` the ring compared a trial-squad count with a
        population that also held the operator's own users.
        """
        if not squad_uuids:
            return SquadActivity(online=0, week=0)
        now = datetime.now(UTC)
        cutoff = now - timedelta(seconds=self.ONLINE_WINDOW_SECONDS)
        week_cutoff = now - timedelta(days=7)
        online = week = 0
        start = 0
        for _ in range(self._USERS_MAX_PAGES):
            try:
                data = await self._request(
                    "GET", f"/users?size={self._USERS_PAGE_SIZE}&start={start}"
                )
            except RemnawaveError:
                return None
            users = data.get("users", []) if isinstance(data, dict) else []
            if not users:
                break
            for raw in users:
                try:
                    user = PanelUser.model_validate(raw)
                except ValidationError:
                    continue
                seen = _parse_iso(user.traffic.online_at)
                if seen is None or seen < week_cutoff:
                    continue
                if any(ref.uuid in squad_uuids for ref in user.active_internal_squads):
                    week += 1
                    if seen >= cutoff:
                        online += 1
            if len(users) < self._USERS_PAGE_SIZE:
                break
            start += self._USERS_PAGE_SIZE
        else:
            logger.warning(
                "squad_online_count: hit the %d-page cap; count is a floor", self._USERS_MAX_PAGES
            )
        return SquadActivity(online=online, week=week)

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

    async def subscription(self, username: str) -> tuple[Subscription, dict[str, str]]:
        """The user's own subscription paired with a remark NAME -> config link map.

        Single source of truth for the location picker: the picker's names and the link handed back
        on a pick both come from this one response, so they can never cross-index (the v1 bug). We
        take the by-username ``ssConfLinks`` map, else parse remarks out of ``links[]``.

        VERIFY: 2.8 and 3.4 both build ``ssConfLinks`` as ``{}`` and fill ``links[]`` for this
        admin endpoint (it resolves hosts as authenticated), so ``links[]`` is what answers. With
        default subscription settings it is never empty: a user with no host, or one that is not
        ACTIVE, gets the panel's placeholder links (customRemarks: "→ No hosts found",
        "⌛ Subscription expired", …) — a location allowlist drops those, as no squad host carries
        that remark (an EMPTY bot allowlist keeps everything, placeholders included). It is empty
        only when such a placeholder list was cleared or every host is excluded from
        XRAY_BASE64, and it is returned as the real answer it is. There is
        deliberately no second endpoint to fall back to: the one this used to try
        (``/subscriptions/raw/{shortUuid}``) exists in no panel version, and its 404 read as
        "account gone", deleting a live trial (a LIMITED one's revive path included).
        """
        sub = await self.get_subscription(username)
        links = dict(sub.ss_conf_links)
        if not links:
            links = _links_from_list(sub.links)
        return sub, links

    async def squad_location_names(self, squad_uuid: str) -> list[str]:
        """Location remark names available to a squad — and ONLY that squad.

        VERIFY (live contract): there's no direct squad->hosts endpoint, so we match by inbound
        UUID. A squad's ``inbounds[]`` are config-profile inbounds whose OWN id is ``uuid``; a host
        points at an inbound via ``host.inbound.configProfileInboundUuid``. So the join is
        ``squad.inbounds[].uuid`` == ``host.inbound.configProfileInboundUuid`` (dropping hosts whose
        squad rule keeps this squad out — ``Host.serves_squad``, which reads both the ≤3.3
        exclusion list and 3.4's EXCLUDE/ALLOW_ONLY) — NOT the squad's non-existent
        ``configProfileInboundUuid`` (matching on that gave an empty set every time, which then
        leaked EVERY host into one squad).

        Returns strictly the matched squad's locations. An unknown squad, or a squad no enabled host
        serves, yields ``[]`` (logged) — never every host. Silently falling back to all hosts is the
        exact "brings every squad's locations" bug this scoping is meant to prevent.
        """
        squads = await self.list_internal_squads()
        hosts = await self.list_hosts()
        # Hidden hosts are served by neither the subscription nor the picker: offering one produces
        # a name that no link carries, which is exactly what makes a pick resolve to nothing.
        enabled = [h for h in hosts if not h.is_disabled and not h.is_hidden]
        squad = next((s for s in squads if s.uuid == squad_uuid), None)
        if squad is None:
            logger.warning(
                "squad_location_names: squad %s not found (%d squads)", squad_uuid, len(squads)
            )
            return []

        inbound_uuids = {i.uuid for i in squad.inbounds if i.uuid}
        matched = [
            h.remark
            for h in enabled
            if h.inbound.config_profile_inbound_uuid in inbound_uuids and h.serves_squad(squad_uuid)
        ]
        if not matched:
            logger.warning(
                "squad_location_names: squad %s (%d inbounds) matched no enabled host",
                squad_uuid,
                len(inbound_uuids),
            )
        return _unique(matched)
