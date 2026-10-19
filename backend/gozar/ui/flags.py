"""A location's country, and its flag drawn as a premium emoji — in the picker and in the config.

A location is a host REMARK (matched by name everywhere; nothing here changes the name a pick
resolves by). Its country comes from, in order: a flag emoji in the remark (covers every country),
a country name in Persian or English, or a bare two-letter code — the same order as the website's
``flagCC`` (``frontend/site/components/widget/flags.ts``), whose keyword table this one contains.

Drawing: on a keyboard button the flag becomes the button's icon (``icon_custom_emoji_id``) and
leaves the label; in a message it becomes ``<tg-emoji>`` with the flag as the alternative text. A
remark that names its country without a flag gets the premium flag added in front. With icons off
(no Premium, 🎨, ``/simple``) everything is exactly the remark.
"""

from __future__ import annotations

import html
import re

from aiogram.types import InlineKeyboardMarkup

from gozar.ui.icons import FLAGS, VS16
from gozar.ui.look import Look

_RI = "[\U0001f1e6-\U0001f1ff]"
# a flag (two regional indicators), with the variation selector / spaces around it
_LEAD_FLAG = re.compile(f"^\\s*({_RI}{_RI}){VS16}?\\s*")
_TAIL_FLAG = re.compile(f"\\s*({_RI}{_RI}){VS16}?\\s*$")
_ANY_FLAG = re.compile(f"{_RI}{_RI}")
# what the site's ``locName`` strips from the front: pictographs, regional indicators, VS16, space
_LEAD_PICTO = re.compile(r"^[\U0001f000-\U0001faff☀-➿\U0001f1e6-\U0001f1ff️\s]+")

#: Country names → ISO code (lower case). Persian + English, as the site has them, plus the
#: Persian names tunnelbot used for node countries. A remark may say «آلمان ۲», "Germany-2" or
#: «سرور هلند»: a name counts when it stands as a whole word.
KEYWORD: dict[str, str] = {
    "germany": "de", "deutschland": "de", "آلمان": "de",
    "ukraine": "ua", "اوکراین": "ua",
    "usa": "us", "united states": "us", "america": "us", "آمریکا": "us", "امریکا": "us",
    "turkey": "tr", "türkiye": "tr", "turkiye": "tr", "ترکیه": "tr",
    "france": "fr", "فرانسه": "fr",
    "uk": "gb", "united kingdom": "gb", "u-kingdom": "gb", "u kingdom": "gb", "britain": "gb",
    "great britain": "gb", "england": "gb", "انگلیس": "gb", "انگلستان": "gb", "بریتانیا": "gb",
    "بریتانیا کبیر": "gb",
    "netherlands": "nl", "holland": "nl", "هلند": "nl",
    "canada": "ca", "کانادا": "ca",
    "spain": "es", "españa": "es", "espana": "es", "اسپانیا": "es",
    "sweden": "se", "سوئد": "se",
    "japan": "jp", "ژاپن": "jp",
    "australia": "au", "استرالیا": "au",
    "emirates": "ae", "uae": "ae", "united arab emirates": "ae", "dubai": "ae", "امارات": "ae",
    "italy": "it", "italia": "it", "ایتالیا": "it",
    "russia": "ru", "روسیه": "ru",
    "poland": "pl", "لهستان": "pl",
    "romania": "ro", "رومانی": "ro",
    "ireland": "ie", "ایرلند": "ie",
    "belgium": "be", "بلژیک": "be",
    "austria": "at", "اتریش": "at",
    "switzerland": "ch", "swiss": "ch", "سوئیس": "ch", "سوییس": "ch",
    "finland": "fi", "فنلاند": "fi",
    "denmark": "dk", "دانمارک": "dk",
    "norway": "no", "نروژ": "no",
    "portugal": "pt", "پرتغال": "pt",
    "india": "in", "هند": "in",
    "brazil": "br", "برزیل": "br",
    "south korea": "kr", "korea": "kr", "کره جنوبی": "kr", "کره": "kr",
    "singapore": "sg", "سنگاپور": "sg",
    "indonesia": "id", "اندونزی": "id",
    "mexico": "mx", "مکزیک": "mx",
    "hungary": "hu", "مجارستان": "hu",
    "iran": "ir", "ایران": "ir",
    "china": "cn", "چین": "cn",
    "saudi arabia": "sa", "saudi": "sa", "عربستان": "sa",
    "qatar": "qa", "قطر": "qa",
    "greece": "gr", "یونان": "gr",
    "czech": "cz", "czechia": "cz", "چک": "cz",
    "bulgaria": "bg", "بلغارستان": "bg",
    "serbia": "rs", "صربستان": "rs",
    "israel": "il", "اسرائیل": "il",
    "hong kong": "hk", "hongkong": "hk", "هنگ کنگ": "hk", "هنگ‌کنگ": "hk",
    "south africa": "za", "آفریقای جنوبی": "za",
    "argentina": "ar", "آرژانتین": "ar",
    "nigeria": "ng", "نیجریه": "ng",
    "chile": "cl", "شیلی": "cl",
    "luxembourg": "lu", "لوکزامبورگ": "lu",
    "estonia": "ee", "استونی": "ee",
    "latvia": "lv", "لتونی": "lv",
    "lithuania": "lt", "لیتوانی": "lt",
    "kazakhstan": "kz", "قزاقستان": "kz",
    "armenia": "am", "ارمنستان": "am",
    "georgia": "ge", "گرجستان": "ge",
    "azerbaijan": "az", "آذربایجان": "az",
    "vietnam": "vn", "ویتنام": "vn",
    "thailand": "th", "تایلند": "th",
    "malaysia": "my", "مالزی": "my",
    "taiwan": "tw", "تایوان": "tw",
    "moldova": "md", "مولداوی": "md",
    "bahrain": "bh", "بحرین": "bh",
    "oman": "om", "عمان": "om",
    "iraq": "iq", "عراق": "iq",
    "cyprus": "cy", "قبرس": "cy",
    "iceland": "is", "ایسلند": "is",
}  # fmt: skip
_BY_LENGTH = sorted(KEYWORD.items(), key=lambda kv: len(kv[0]), reverse=True)


def flag_emoji(code: str) -> str:
    """'DE' -> '🇩🇪' (two regional indicator symbols)."""
    return "".join(chr(0x1F1E6 + ord(c) - ord("A")) for c in code.upper())


def _code_of_flag(flag: str) -> str:
    return "".join(chr(ord(c) - 0x1F1E6 + ord("A")) for c in flag)


def _whole_word(name: str, word: str) -> bool:
    """``word`` appears in ``name`` with no letter right before or after it (so «چک» never
    matches inside «کوچک» and "uk" never inside "duke")."""
    start = name.find(word)
    while start != -1:
        end = start + len(word)
        before = name[start - 1] if start > 0 else ""
        after = name[end] if end < len(name) else ""
        if not before.isalpha() and not after.isalpha():
            return True
        start = name.find(word, start + 1)
    return False


def country_code(remark: str) -> str | None:
    """The country a location remark names (upper-case ISO alpha-2), or None."""
    flag = _ANY_FLAG.search(remark)
    if flag:  # any flag names its country, premium flag or not (Syria's is left out of FLAGS)
        return _code_of_flag(flag.group(0))
    name = _LEAD_PICTO.sub("", remark).strip().lower() or remark.strip().lower()
    for word, code in _BY_LENGTH:
        if name == word or _whole_word(name, word):
            return code.upper()
    if re.fullmatch(r"[a-z]{2}", name) and name.upper() in FLAGS:
        return name.upper()
    return None


def split_flag(remark: str) -> tuple[str | None, str]:
    """``("DE", "آلمان ۲")`` for «🇩🇪 آلمان ۲» (a leading or trailing flag); ``(None, remark)`` when
    the remark carries no flag at either end, or nothing would be left without it."""
    for rx in (_LEAD_FLAG, _TAIL_FLAG):
        m = rx.search(remark)
        if m:
            rest = (remark[: m.start()] + remark[m.end() :]).strip()
            if rest:
                return _code_of_flag(m.group(1)), rest
    return None, remark


def with_flag(remark: str) -> str:
    """The remark with a plain flag emoji in front when it names its country without one (a
    console cell; the sender turns the flag into a premium one). Unchanged otherwise."""
    if _ANY_FLAG.search(remark):
        return remark
    code = country_code(remark)
    return f"{flag_emoji(code)} {remark}" if code else remark


def location_button(remark: str, look: Look) -> tuple[str, str | None]:
    """A picker button for ``remark``: ``(label, icon id)``. With a premium flag the label loses its
    own flag emoji (the icon stands in for it); without one it is the remark, untouched."""
    code, rest = split_flag(remark)
    if code is not None:
        eid = look.flag_id(code)
        return (rest, eid) if eid else (remark, None)
    eid = look.flag_id(country_code(remark))
    return remark, eid


def location_html(remark: str, look: Look) -> str:
    """``remark`` for a message body — escaped, its flag drawn as a premium emoji (one added in
    front when the remark only names its country)."""
    code = country_code(remark)
    eid = look.flag_id(code)
    if not eid or code is None:
        return html.escape(remark)
    flag = flag_emoji(code)

    def tag(m: re.Match[str]) -> str:
        return f'<tg-emoji emoji-id="{eid}">{m.group(0)}</tg-emoji>'

    if _ANY_FLAG.search(remark):
        return _ANY_FLAG.sub(tag, html.escape(remark), count=1)
    return f'<tg-emoji emoji-id="{eid}">{flag}</tg-emoji> {html.escape(remark)}'


def flag_keyboard(
    markup: InlineKeyboardMarkup, remarks: dict[str, str], look: Look
) -> InlineKeyboardMarkup:
    """The picker keyboard with premium flags: each button whose callback data is in ``remarks``
    (callback data → remark) gets its flag icon. Chrome buttons are left alone. Returns the same
    object when nothing changed, so a caller can tell a themed keyboard from the plain one."""
    if not look.icons_on:
        return markup
    changed = False
    rows = []
    for row in markup.inline_keyboard:
        new_row = []
        for b in row:
            remark = remarks.get(b.callback_data or "")
            if remark is not None and b.icon_custom_emoji_id is None:
                label, eid = location_button(remark, look)
                if eid:
                    b = b.model_copy(update={"text": label, "icon_custom_emoji_id": eid})
                    changed = True
            new_row.append(b)
        rows.append(new_row)
    return markup.model_copy(update={"inline_keyboard": rows}) if changed else markup
