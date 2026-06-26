"""Pure helpers for parsing the remark (location name) out of a raw config link.

VERIFY: the remark location is format-dependent — vmess carries it as the base64 JSON ``ps`` field,
while vless / trojan / shadowsocks carry it as the URL ``#fragment``. Returns None when absent.
"""

from __future__ import annotations

import base64
import binascii
import json
from urllib.parse import unquote


def parse_remark(link: str) -> str | None:
    link = link.strip()
    scheme, sep, rest = link.partition("://")
    if not sep or not rest:
        return None
    if scheme.lower() == "vmess":
        try:
            padded = rest + "=" * (-len(rest) % 4)
            payload = json.loads(base64.b64decode(padded).decode("utf-8", "ignore"))
        except (binascii.Error, ValueError):
            return None
        ps = payload.get("ps") if isinstance(payload, dict) else None
        return ps.strip() or None if isinstance(ps, str) else None
    # vless / trojan / ss / etc.: the remark is the URL fragment.
    if "#" in link:
        return unquote(link.split("#", 1)[1]).strip() or None
    return None
