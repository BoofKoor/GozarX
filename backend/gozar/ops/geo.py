"""The country of an IP address — for a new node's flag in the panel and its suggested name.

Asked from the bot's own server, which is outside Iran and has open internet: ipwho.is →
ipinfo.io → country.is, the first answer wins, all over HTTPS (TLS verified — the shared client's).
A reserved/private address is "XX" (the panel's own default). Every provider gets one bounded
attempt.
"""

from __future__ import annotations

import ipaddress
import logging
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

import httpx

logger = logging.getLogger("gozar.ops.geo")

#: Persian names for the countries VPN nodes usually live in; anything else shows the provider's
#: (English) name.
FA_NAMES = {
    "DE": "آلمان", "NL": "هلند", "FI": "فنلاند", "FR": "فرانسه", "GB": "انگلیس", "US": "آمریکا",
    "TR": "ترکیه", "AE": "امارات", "RU": "روسیه", "SE": "سوئد", "CA": "کانادا", "PL": "لهستان",
    "AT": "اتریش", "CH": "سوئیس", "IR": "ایران", "AM": "ارمنستان", "LT": "لیتوانی", "LV": "لتونی",
    "EE": "استونی", "RO": "رومانی", "BG": "بلغارستان", "CZ": "چک", "HU": "مجارستان", "IT": "ایتالیا",
    "ES": "اسپانیا", "JP": "ژاپن", "SG": "سنگاپور", "HK": "هنگ‌کنگ", "KZ": "قزاقستان", "GE": "گرجستان",
    "NO": "نروژ", "DK": "دانمارک", "BE": "بلژیک", "IE": "ایرلند", "PT": "پرتغال", "UA": "اوکراین",
    "MD": "مولداوی", "AZ": "آذربایجان", "IN": "هند", "QA": "قطر", "SA": "عربستان", "BH": "بحرین",
    "OM": "عمان", "IQ": "عراق", "CY": "قبرس", "GR": "یونان", "RS": "صربستان", "LU": "لوکزامبورگ",
    "IS": "ایسلند", "KR": "کره جنوبی", "AU": "استرالیا", "BR": "برزیل", "ID": "اندونزی",
}  # fmt: skip


@dataclass
class GeoInfo:
    ip: str
    code: str = "XX"  # ISO 3166-1 alpha-2, upper case; "XX" = unknown
    country: str = ""  # English name from the provider
    isp: str = ""
    source: str = ""  # which service answered ("reserved" / "" when none)

    @property
    def flag(self) -> str:
        return flag_of(self.code) or "🏳️"

    @property
    def label(self) -> str:
        """e.g. '🇩🇪 آلمان (DE)'."""
        if not known(self.code):
            return "🏳️ نامشخص (XX)"
        name = FA_NAMES.get(self.code) or self.country or self.code
        return f"{self.flag} {name} ({self.code})"


def known(code: str | None) -> bool:
    """A real ISO alpha-2 code (not the panel's "XX" for "unknown")."""
    return bool(code) and len(code) == 2 and code.isalpha() and code.upper() != "XX"


def flag_of(code: str | None) -> str:
    """'DE' → '🇩🇪'; '' for an unknown country."""
    if not known(code):
        return ""
    return "".join(chr(0x1F1E6 + ord(c) - ord("A")) for c in code.upper())


def country_name(code: str | None) -> str:
    """The country as a person reading Persian names it («آلمان»); the code when the table has no
    name for it, '' when unknown."""
    if not known(code):
        return ""
    return FA_NAMES.get(code.upper(), code.upper())


def is_public(ip: str) -> bool:
    try:
        return ipaddress.ip_address(ip).is_global
    except ValueError:
        return False


def _ipwho(d: Any) -> tuple[str, str, str] | None:
    if isinstance(d, dict) and d.get("success") and d.get("country_code"):
        conn = d.get("connection") or {}
        return d["country_code"], d.get("country", ""), conn.get("isp") or conn.get("org") or ""
    return None


def _ipinfo(d: Any) -> tuple[str, str, str] | None:
    if isinstance(d, dict) and d.get("country") and not d.get("bogon"):
        return d["country"], "", d.get("org", "")
    return None


def _country_is(d: Any) -> tuple[str, str, str] | None:
    if isinstance(d, dict) and isinstance(d.get("country"), str):
        return d["country"], "", ""
    return None


PROVIDERS = [
    ("ipwho.is", "https://ipwho.is/{ip}", _ipwho),
    ("ipinfo.io", "https://ipinfo.io/{ip}/json", _ipinfo),
    ("country.is", "https://api.country.is/{ip}", _country_is),
]


async def lookup(
    http: httpx.AsyncClient,
    ip: str,
    *,
    seconds: float = 8,
    debug: Callable[[str], None] | None = None,
    providers: list | None = None,
) -> GeoInfo:
    dbg = debug or (lambda _line: None)
    if not is_public(ip):
        return GeoInfo(ip, source="reserved")
    headers = {"User-Agent": "gozar", "Accept": "application/json"}
    for name, url, parse in providers or PROVIDERS:
        try:
            r = await http.get(url.format(ip=ip), headers=headers, timeout=seconds)
            got = parse(r.json())
        except (httpx.HTTPError, ValueError) as e:
            dbg(f"[geo] {name}: {type(e).__name__}")
            continue
        if got and len(got[0]) == 2 and got[0].isalpha():
            dbg(f"[geo] {ip} -> {got[0]} ({name})")
            return GeoInfo(ip, got[0].upper(), got[1], got[2], name)
        dbg(f"[geo] {name}: no answer for {ip}")
    return GeoInfo(ip)
