"""Remnawave client request building + response parsing via httpx.MockTransport (no network)."""

from __future__ import annotations

import json
from collections.abc import Callable
from datetime import UTC, datetime

import httpx
import pytest

from gozar.remnawave.client import RemnawaveClient, _online_usernames_from
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


async def test_squad_location_names_matches_by_inbound() -> None:
    squads = {
        "response": {
            "internalSquads": [
                {
                    "uuid": "sq1",
                    "name": "Trial",
                    "inbounds": [{"uuid": "i1", "configProfileInboundUuid": "p1"}],
                }
            ]
        }
    }
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

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/api/internal-squads":
            return httpx.Response(200, json=squads)
        if request.url.path == "/api/hosts":
            return httpx.Response(200, json=hosts)
        return httpx.Response(404)

    names = await _client(handler).squad_location_names("sq1")
    assert names == ["Germany"]  # Finland: wrong inbound; Excluded: squad excluded


async def test_non_2xx_raises_remnawave_error() -> None:
    client = _client(lambda req: httpx.Response(500, json={"message": "boom"}))
    with pytest.raises(RemnawaveError):
        await client.create_trial_user("t", 1, datetime(2030, 1, 1, tzinfo=UTC), [])


def test_online_usernames_parser_tolerates_shapes() -> None:
    # bare list of names
    assert _online_usernames_from(["a", "b", "a"]) == {"a", "b"}
    # list of user dicts (username or name)
    assert _online_usernames_from([{"username": "a"}, {"name": "b"}, {"x": 1}]) == {"a", "b"}
    # wrapper dicts under a few likely keys
    assert _online_usernames_from({"onlineUsers": ["a"]}) == {"a"}
    assert _online_usernames_from({"users": [{"username": "b"}]}) == {"b"}
    # nobody online is a valid answer (empty set, not None)
    assert _online_usernames_from([]) == set()
    # unrecognised shapes -> None so the caller falls back to the DB count
    assert _online_usernames_from({"unexpected": 1}) is None
    assert _online_usernames_from(42) is None


async def test_online_usernames_endpoint_returns_set() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/api/system/stats/online"
        return httpx.Response(200, json={"response": ["g_1", "g_2"]})

    assert await _client(handler).online_usernames() == {"g_1", "g_2"}


async def test_online_usernames_returns_none_when_endpoint_missing() -> None:
    # a panel that doesn't expose the endpoint -> None (a single bounded attempt, no raise)
    assert await _client(lambda req: httpx.Response(404)).online_usernames() is None
