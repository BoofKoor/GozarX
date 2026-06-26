"""Phase 4 client additions: ``update_traffic_limit`` by uuid + ``subscription()`` link resolution
(ssConfLinks -> parsed links[] -> raw endpoint, shape varies). httpx MockTransport; no network.
"""

from __future__ import annotations

import json
from collections.abc import Callable

import httpx

from gozar.remnawave.client import RemnawaveClient

Handler = Callable[[httpx.Request], httpx.Response]


def _client(handler: Handler) -> RemnawaveClient:
    http = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    return RemnawaveClient(http, "https://panel.example.com", "tok")


async def test_update_traffic_limit_patches_by_uuid() -> None:
    seen: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["method"] = request.method
        seen["path"] = request.url.path
        seen["body"] = json.loads(request.content)
        return httpx.Response(200, json={"response": {"uuid": "u1", "username": "t_1"}})

    user = await _client(handler).update_traffic_limit("u1", 2048)
    assert seen["method"] == "PATCH"
    assert seen["path"] == "/api/users"
    assert seen["body"] == {"uuid": "u1", "trafficLimitBytes": 2048}  # keyed by uuid, not username
    assert user.uuid == "u1"


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
