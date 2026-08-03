"""Pure helpers for parsing the remark (location name) out of a raw config link.

VERIFY: the remark location is format-dependent — vmess carries it as the base64 JSON ``ps`` field,
while vless / trojan / shadowsocks carry it as the URL ``#fragment``. Returns None when absent.
"""

from __future__ import annotations

import base64
import binascii
import json
import re
import unicodedata
from urllib.parse import unquote

# A Remnawave host remark may carry template tokens ("Germany {{TRAFFIC_USED}}") which the panel
# RENDERS before it reaches a config link. So the same location arrives as two different strings:
# the raw remark from GET /api/hosts, and the rendered fragment on the link. Comparing those two
# verbatim never matches — the squad allowlist then intersects to nothing and, because an empty
# allowlist used to mean "keep everything", every host leaked through. Both sides are put through
# normalize_remark() before any comparison.
_TEMPLATE = re.compile(r"\{\{.*?\}\}")
_WS = re.compile(r"\s+")


def normalize_remark(remark: str) -> str:
    """A comparison key for a location name: template tokens dropped, spacing/width/case folded.

    NOT for display — the original string is what gets shown and what keys the link map; this is
    only ever the join key between a host remark and a link fragment. NFKC folds the full-width and
    Arabic-presentation forms a panel UI can introduce, so "آلمان" typed two ways still matches.
    """
    text = unicodedata.normalize("NFKC", _TEMPLATE.sub(" ", remark))
    # Zero-width joiner/non-joiner are invisible but break equality on Persian names.
    text = text.replace("‌", " ").replace("‍", "").replace("﻿", "")
    return _WS.sub(" ", text).strip().casefold()


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
