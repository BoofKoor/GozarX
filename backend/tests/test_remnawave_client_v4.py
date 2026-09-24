"""Phase 4 client additions: ``update_traffic_limit`` by username + ``subscription()`` link
resolution (ssConfLinks -> parsed links[] -> raw endpoint, shape varies). httpx MockTransport; no
network.
"""

from __future__ import annotations

import json
from collections.abc import Callable

import httpx
import pytest

from gozar.remnawave.client import RemnawaveClient
from gozar.remnawave.errors import RemnawaveError

Handler = Callable[[httpx.Request], httpx.Response]


def _client(handler: Handler) -> RemnawaveClient:
    http = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    return RemnawaveClient(http, "https://panel.example.com", "tok")


async def test_update_traffic_limit_patches_by_username() -> None:
    seen: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["method"] = request.method
        seen["path"] = request.url.path
        seen["body"] = json.loads(request.content)
        return httpx.Response(200, json={"response": {"id": 42, "username": "t_1"}})

    user = await _client(handler).update_traffic_limit("t_1", 2048)
    assert seen["method"] == "PATCH"
    assert seen["path"] == "/api/users"
    # Keyed by USERNAME: 2.x accepts uuid|username, 3.x id|username — the name is the one key both
    # take. A uuid-keyed body is stripped to nothing by 3.x and refused with a 400.
    assert seen["body"] == {"username": "t_1", "trafficLimitBytes": 2048}
    assert user is not None and user.username == "t_1"


async def test_update_traffic_limit_on_a_gone_account_is_none() -> None:
    client = _client(lambda r: httpx.Response(404, json={"message": "User not found"}))
    assert await client.update_traffic_limit("t_1", 2048) is None


async def test_update_traffic_limit_transient_failure_raises() -> None:
    client = _client(lambda r: httpx.Response(500, json={"message": "Update user error"}))
    with pytest.raises(RemnawaveError):
        await client.update_traffic_limit("t_1", 2048)


async def test_subscription_prefers_ssconflinks() -> None:
    payload = {
        "response": {
            "links": ["vless://a#Germany"],
            "ssConfLinks": {"Germany": "vless://de#Germany"},
            "user": {"shortUuid": "su1"},
        }
    }
    raw_calls = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        if "/subscriptions/raw/" in request.url.path:
            raw_calls["n"] += 1
            return httpx.Response(200, json={"response": []})
        return httpx.Response(200, json=payload)

    _sub, links = await _client(handler).subscription("t_1")
    assert links == {"Germany": "vless://de#Germany"}
    assert raw_calls["n"] == 0  # ssConfLinks present -> no raw fallback


async def test_subscription_parses_links_when_no_ssconflinks() -> None:
    payload = {
        "response": {
            "links": ["vless://a#Germany", "vless://b#Finland"],
            "ssConfLinks": {},
            "user": {"shortUuid": "su1"},
        }
    }
    sub_link = await _client(lambda r: httpx.Response(200, json=payload)).subscription("t_1")
    assert sub_link[1] == {"Germany": "vless://a#Germany", "Finland": "vless://b#Finland"}


async def test_subscription_falls_back_to_raw_link_list() -> None:
    sub_payload = {"response": {"links": [], "ssConfLinks": {}, "user": {"shortUuid": "su1"}}}
    raw_payload = {"response": ["vless://a#Germany", "vless://b#Finland"]}

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/api/subscriptions/raw/su1":
            return httpx.Response(200, json=raw_payload)
        return httpx.Response(200, json=sub_payload)

    _sub, links = await _client(handler).subscription("t_1")
    assert links == {"Germany": "vless://a#Germany", "Finland": "vless://b#Finland"}


async def test_subscription_falls_back_to_raw_remark_map() -> None:
    sub_payload = {"response": {"links": [], "ssConfLinks": {}, "user": {"shortUuid": "su1"}}}
    raw_payload = {"response": {"Germany": "vless://de", "Finland": "vless://fi"}}

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/api/subscriptions/raw/su1":
            return httpx.Response(200, json=raw_payload)
        return httpx.Response(200, json=sub_payload)

    _sub, links = await _client(handler).subscription("t_1")
    assert links == {"Germany": "vless://de", "Finland": "vless://fi"}
