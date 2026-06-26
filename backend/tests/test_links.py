"""Pure ``parse_remark`` tests — the remark (location name) lives in the vmess ``ps`` field or the
URL ``#fragment`` (vless/trojan/ss). No network, no panel.
"""

from __future__ import annotations

import base64
import json

from gozar.remnawave.links import parse_remark


def _vmess(payload: dict) -> str:
    raw = base64.b64encode(json.dumps(payload).encode()).decode()
    return f"vmess://{raw}"


def test_vless_fragment() -> None:
    assert parse_remark("vless://uuid@host:443?type=tcp&security=reality#Germany") == "Germany"


def test_trojan_fragment() -> None:
    assert parse_remark("trojan://pass@host:443?sni=x#Finland-2") == "Finland-2"


def test_shadowsocks_fragment() -> None:
    assert parse_remark("ss://YWVzOnBhc3M@host:8388#Netherlands") == "Netherlands"


def test_urlencoded_fragment_is_decoded() -> None:
    # "%F0%9F%87%A9%F0%9F%87%AA" is the 🇩🇪 flag; "%20" a space.
    assert parse_remark("vless://u@h:443#DE%20%F0%9F%87%A9%F0%9F%87%AA") == "DE 🇩🇪"


def test_vmess_ps_field() -> None:
    assert parse_remark(_vmess({"v": "2", "ps": "United Kingdom", "add": "1.2.3.4"})) == (
        "United Kingdom"
    )


def test_vmess_without_ps_is_none() -> None:
    assert parse_remark(_vmess({"v": "2", "add": "1.2.3.4"})) is None


def test_vmess_invalid_base64_is_none() -> None:
    assert parse_remark("vmess://!!!not base64!!!") is None


def test_fragmentless_link_is_none() -> None:
    assert parse_remark("vless://uuid@host:443?type=tcp") is None


def test_empty_fragment_is_none() -> None:
    assert parse_remark("vless://uuid@host:443#") is None


def test_non_link_is_none() -> None:
    assert parse_remark("not-a-link") is None
    assert parse_remark("") is None
