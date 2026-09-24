"""Remnawave client request building + response parsing via httpx.MockTransport (no network)."""

from __future__ import annotations

import json
from collections.abc import Callable
from datetime import UTC, datetime, timedelta

import httpx
import pytest

from gozar.remnawave.client import RemnawaveClient
from gozar.remnawave.errors import RemnawaveError

Handler = Callable[[httpx.Request], httpx.Response]


def _client(handler: Handler) -> RemnawaveClient:
    http = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    return RemnawaveClient(http, "https://panel.example.com", "tok")


async def test_create_trial_user_request_and_parse() -> None:
    seen: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["method"] = request.method
        seen["url"] = str(request.url)
        seen["auth"] = request.headers.get("authorization")
        seen["body"] = json.loads(request.content)
        return httpx.Response(
            200,
            json={
                "response": {
                    "uuid": "u1",
                    "username": "t_1",
                    "subscriptionUrl": "https://s/x",
                    "trafficLimitBytes": 1000,
                    "userTraffic": {"usedTrafficBytes": 42},
                }
            },
        )

    user = await _client(handler).create_trial_user(
        "t_1", 1000, datetime(2030, 1, 1, tzinfo=UTC), ["sq1"]
    )
    assert seen["method"] == "POST"
    assert seen["url"] == "https://panel.example.com/api/users"
    assert seen["auth"] == "Bearer tok"
    assert seen["body"] == {
        "username": "t_1",
        "expireAt": "2030-01-01T00:00:00+00:00",
        "trafficLimitBytes": 1000,
        "trafficLimitStrategy": "NO_RESET",
        "status": "ACTIVE",
        "activeInternalSquads": ["sq1"],
    }
    assert user.uuid == "u1"
    assert user.subscription_url == "https://s/x"
    assert user.traffic.used_bytes == 42


async def test_get_user_404_returns_none() -> None:
    client = _client(lambda req: httpx.Response(404, json={"message": "not found"}))
    assert await client.get_user("nope") is None


# GetFullUserResponseModel as each major serialises it (trimmed to what we read + the keys). 2.x
# sends BOTH `uuid` and a numeric `id` but validates `/users/{…}` paths as a UUID; 3.0 dropped the
# uuid column and keys those paths by `id`. One build must drive both, so `ref` reads the record.
_USER_V2 = {
    "uuid": "0b5e0cb5-8c3d-4f5a-9d6e-1f2a3b4c5d6e",
    "id": 7,
    "shortUuid": "s2",
    "username": "g1_100",
    "status": "ACTIVE",
    "trafficLimitBytes": 1024,
    "expireAt": "2030-01-01T00:00:00.000Z",
    "subscriptionUrl": "https://sub/s2",
    "activeInternalSquads": [{"uuid": "sq1", "name": "Trial"}],
    "userTraffic": {"usedTrafficBytes": 5, "onlineAt": None},
}
_USER_V3 = {key: value for key, value in _USER_V2.items() if key != "uuid"} | {"id": 42}


def _delete_flow_handler(
    user: dict, seen: list[tuple[str, str]], delete: httpx.Response
) -> Handler:
    def handler(request: httpx.Request) -> httpx.Response:
        seen.append((request.method, request.url.path))
        if request.method == "GET":
            return httpx.Response(200, json={"response": user})
        return delete

    return handler


async def test_delete_user_by_username_keys_off_the_uuid_on_panel_2() -> None:
    seen: list[tuple[str, str]] = []
    deleted = httpx.Response(200, json={"response": {"isDeleted": True}})
    client = _client(_delete_flow_handler(_USER_V2, seen, deleted))

    assert await client.delete_user_by_username("g1_100") is True
    assert seen == [
        ("GET", "/api/users/by-username/g1_100"),
        ("DELETE", f"/api/users/{_USER_V2['uuid']}"),  # 2.x: the uuid, never the numeric id
    ]


async def test_delete_user_by_username_keys_off_the_id_on_panel_3() -> None:
    # 3.x answers DELETE with 204 and no body — still a successful delete.
    seen: list[tuple[str, str]] = []
    client = _client(_delete_flow_handler(_USER_V3, seen, httpx.Response(204)))

    assert await client.delete_user_by_username("g1_100") is True
    assert seen == [("GET", "/api/users/by-username/g1_100"), ("DELETE", "/api/users/42")]


async def test_delete_user_by_username_gone_is_false_without_a_delete() -> None:
    seen: list[tuple[str, str]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append((request.method, request.url.path))
        return httpx.Response(404, json={"message": "User not found"})

    assert await _client(handler).delete_user_by_username("g1_100") is False
    assert seen == [("GET", "/api/users/by-username/g1_100")]


async def test_delete_user_by_username_without_any_key_calls_nothing_destructive() -> None:
    # A record we can't key (neither uuid nor id) must never turn into DELETE /api/users/ (the
    # collection) — it reads as "nothing to delete".
    seen: list[tuple[str, str]] = []
    keyless = {"username": "g1_100", "status": "EXPIRED"}
    client = _client(_delete_flow_handler(keyless, seen, httpx.Response(500)))

    assert await client.delete_user_by_username("g1_100") is False
    assert seen == [("GET", "/api/users/by-username/g1_100")]


@pytest.mark.parametrize(("user", "ref"), [(_USER_V2, _USER_V2["uuid"]), (_USER_V3, "42")])
async def test_reset_user_traffic_uses_the_panels_own_key(user: dict, ref: str) -> None:
    seen: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request.url.path)
        return httpx.Response(200, json={"response": user})  # both majors answer with the user

    client = _client(handler)
    panel_user = await client.get_user("g1_100")
    assert panel_user is not None and panel_user.ref == ref
    assert await client.reset_user_traffic(panel_user.ref) is True
    assert seen[-1] == f"/api/users/{ref}/actions/reset-traffic"


async def test_get_subscription_parses_ssconflinks() -> None:
    payload = {
        "response": {
            "links": ["vless://a"],
            "ssConfLinks": {"Germany": "vless://de"},
            "user": {"daysLeft": 3, "trafficUsedBytes": "5"},
        }
    }
    sub = await _client(lambda req: httpx.Response(200, json=payload)).get_subscription("t_1")
    assert sub.links == ["vless://a"]
    assert sub.ss_conf_links == {"Germany": "vless://de"}
    assert sub.user.days_left == 3
    assert sub.user.traffic_used_bytes == 5


def _squads_hosts_handler(squads: dict, hosts: dict) -> Handler:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/api/internal-squads":
            return httpx.Response(200, json=squads)
        if request.url.path == "/api/hosts":
            return httpx.Response(200, json=hosts)
        return httpx.Response(404)

    return handler


# Live-contract shape: a squad's `inbounds[]` are config-profile inbounds keyed by their OWN `uuid`
# (they carry NO `configProfileInboundUuid`); a host points at an inbound via its
# `inbound.configProfileInboundUuid`. So the join is squad `uuid` == host inbound uuid.
_SQUADS = {
    "response": {
        "internalSquads": [
            {
                "uuid": "sq1",
                "name": "Trial",
                "inbounds": [{"uuid": "p1", "tag": "steal", "type": "vless", "profileUuid": "pr1"}],
            }
        ]
    }
}


async def test_squad_location_names_matches_by_inbound() -> None:
    hosts = {
        "response": [
            {"remark": "Germany", "inbound": {"configProfileInboundUuid": "p1"}},
            {"remark": "Finland", "inbound": {"configProfileInboundUuid": "pX"}},
            {
                "remark": "Excluded",
                "inbound": {"configProfileInboundUuid": "p1"},
                "excludedInternalSquads": ["sq1"],
            },
        ]
    }
    names = await _client(_squads_hosts_handler(_SQUADS, hosts)).squad_location_names("sq1")
    assert names == ["Germany"]  # Finland: wrong inbound; Excluded: squad excluded


async def test_squad_location_names_reads_panel_3_4_squad_modes() -> None:
    # 3.4 replaced `excludedInternalSquads` with `internalSquads: {mode, squads}`, so a 3.4 host
    # carries only the latter. Read the old way, every rule below was ignored: the EXCLUDE host
    # leaked in, and so did an ALLOW_ONLY host reserved for another squad.
    def host(remark: str, mode: str, squads: list[str]) -> dict:
        return {
            "remark": remark,
            "inbound": {"configProfileInboundUuid": "p1"},
            "internalSquads": {"mode": mode, "squads": squads},
        }

    hosts = {
        "response": [
            host("Germany", "EXCLUDE", []),  # excludes nobody
            host("Finland", "EXCLUDE", ["sq1"]),  # excludes the trial squad
            host("Sweden", "ALLOW_ONLY", ["sq1"]),  # reserved for the trial squad
            host("Norway", "ALLOW_ONLY", ["sq-vip"]),  # reserved for someone else
            host("Poland", "EXCLUDE", ["sq-vip"]),  # excludes only someone else
        ]
    }
    names = await _client(_squads_hosts_handler(_SQUADS, hosts)).squad_location_names("sq1")
    assert names == ["Germany", "Sweden", "Poland"]


async def test_squad_location_names_scopes_to_squad_never_all_hosts() -> None:
    # Regression: when a squad's inbounds match NO host, we must return [] — never leak every host
    # into this one squad (the "brings every squad's locations" bug). Here the squad serves inbound
    # p1, but both hosts belong to a different inbound (pX).
    hosts = {
        "response": [
            {"remark": "Germany", "inbound": {"configProfileInboundUuid": "pX"}},
            {"remark": "Finland", "inbound": {"configProfileInboundUuid": "pX"}},
        ]
    }
    names = await _client(_squads_hosts_handler(_SQUADS, hosts)).squad_location_names("sq1")
    assert names == []


async def test_squad_location_names_unknown_squad_returns_empty() -> None:
    # An unknown squad UUID can't be scoped — return [] (never all hosts).
    hosts = {"response": [{"remark": "Germany", "inbound": {"configProfileInboundUuid": "p1"}}]}
    names = await _client(_squads_hosts_handler(_SQUADS, hosts)).squad_location_names("ghost")
    assert names == []


async def test_non_2xx_raises_remnawave_error() -> None:
    client = _client(lambda req: httpx.Response(500, json={"message": "boom"}))
    with pytest.raises(RemnawaveError):
        await client.create_trial_user("t", 1, datetime(2030, 1, 1, tzinfo=UTC), [])


async def test_system_stats_parses_real_shape() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/api/system/stats"
        return httpx.Response(
            200,
            json={
                "response": {
                    "cpu": {"cores": 8},
                    "memory": {"total": 1000, "free": 400, "used": 600},
                    "uptime": 123456,
                    "users": {"statusCounts": {"ACTIVE": 9, "EXPIRED": 2}, "totalUsers": 11},
                    "onlineStats": {
                        "lastDay": 30,
                        "lastWeek": 70,
                        "neverOnline": 1,
                        "onlineNow": 4,
                    },
                    "nodes": {"totalOnline": 2, "totalBytesLifetime": "9876543210"},
                }
            },
        )

    stats = await _client(handler).system_stats()
    assert stats is not None
    assert stats.online_now == 4 and stats.online_last_day == 30 and stats.never_online == 1
    assert stats.status_counts == {"ACTIVE": 9, "EXPIRED": 2} and stats.total_users == 11
    assert stats.nodes_online == 2 and stats.total_traffic_bytes == 9876543210  # string -> int
    # panel host resources surfaced for the monitoring page
    assert stats.cpu_cores == 8 and stats.mem_total == 1000 and stats.mem_used == 600
    assert stats.uptime_seconds == 123456


async def test_system_stats_returns_none_on_error() -> None:
    # a panel that can't answer -> None (single bounded attempt, no raise; caller falls back to DB)
    assert await _client(lambda req: httpx.Response(500)).system_stats() is None


def _user(username: str, squad: str, *, online_secs_ago: float | None) -> dict:
    """A UserItemInfo row: one squad membership + an onlineAt N seconds ago (or null)."""
    seen = None
    if online_secs_ago is not None:
        seen = (datetime.now(UTC) - timedelta(seconds=online_secs_ago)).isoformat()
    return {
        "username": username,
        "activeInternalSquads": [{"uuid": squad, "name": squad}],
        "userTraffic": {"usedTrafficBytes": 0, "onlineAt": seen},
    }


async def test_squad_online_count_only_counts_recent_members_of_the_squad() -> None:
    users = [
        _user("a", "trial", online_secs_ago=5),  # counts: in squad, seen 5s ago
        _user("b", "trial", online_secs_ago=30),  # counts: in squad, seen 30s ago
        _user("c", "trial", online_secs_ago=120),  # skip: seen 2min ago (stale)
        _user("d", "trial", online_secs_ago=None),  # skip: never online
        _user("e", "personal", online_secs_ago=5),  # skip: online but a different (personal) squad
    ]

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/api/users"
        return httpx.Response(200, json={"response": {"users": users, "total": len(users)}})

    count = await _client(handler).squad_online_count({"trial"})
    assert count == 2


async def test_squad_online_count_empty_squads_is_zero_no_call() -> None:
    def handler(request: httpx.Request) -> httpx.Response:  # pragma: no cover - must not be hit
        raise AssertionError("panel must not be called when no squad is configured")

    assert await _client(handler).squad_online_count(set()) == 0


async def test_squad_online_count_returns_none_on_panel_error() -> None:
    # falls back to the panel-wide figure at the caller (None, not a raise)
    assert await _client(lambda req: httpx.Response(500)).squad_online_count({"trial"}) is None
