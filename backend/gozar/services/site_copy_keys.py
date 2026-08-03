"""The website copy the panel may override, and the in-code default each key falls back to.

Only four site strings were ever editable (hero title/sub, homepage meta) — everything else the
visitor reads is a compile-time constant in ``frontend/site/lib/design-copy.ts``, so "edit the
website" from the panel was mostly impossible.

The pattern here is deliberate and cheap to extend: a ``site_copy_<designKey>`` content row
OVERRIDES the design-copy value of the same key, and an absent/blank row means "use the in-code
one". The site keeps rendering identically on a fresh install and during a backend outage, because
nothing depends on a row existing.

``DEFAULT`` mirrors the site's own copy verbatim so the panel can show the operator exactly what a
key currently says before they change it, and so "reset to default" is a real operation.
"""

from __future__ import annotations

from gozar.db.models.enums import Language

# Prefix that marks a content row as a design-copy override. `site_copy_hero_sub` overrides the
# `hero_sub` key in the site's DESIGN_COPY map.
SITE_COPY_PREFIX = "site_copy_"

# group -> ordered keys. The grouping is what the panel renders as sections; it has no runtime
# meaning, but "hero", "widget", "sections" is how an operator thinks about the page.
SITE_COPY_GROUPS: dict[str, list[str]] = {
    "hero": [
        "hero_eyebrow",
        "hero_h1_a",
        "hero_h1_b",
        "hero_sub",
        "trust1",
        "trust2",
        "trust3",
        "trust4",
    ],
    "widget": ["w_title", "w_sub", "cta_get"],
    "sections": [
        "m_title",
        "loc_eyebrow",
        "loc_title",
        "loc_sub",
        "app_eyebrow",
        "app_title",
        "app_sub",
        "faq_eyebrow",
        "faq_title",
        "faq_sub",
    ],
}

SITE_COPY_KEYS: list[str] = [k for keys in SITE_COPY_GROUPS.values() for k in keys]

# The two longest strings, lifted out so the table below stays inside the line limit.
_HERO_SUB_FA = (
    "هر روز یک کانفیگ آزمایشی رایگان بگیر؛ لوکیشن دلخواهت را انتخاب کن و بدون ثبت‌نام"
    " وصل شو. با دعوت دوستان هم حجم روزانه‌ات بیشتر می‌شود."
)
_HERO_SUB_EN = (
    "Grab a free trial config every day; pick your location and connect with no signup."
    " Invite friends and your daily volume grows too."
)
_FAQ_SUB_FA = "پاسخ سریع به پرتکرارترین سوال‌ها. اگر جوابت این‌جا نبود، از صفحهٔ تماس بپرس."
_FAQ_SUB_EN = (
    "Quick answers to the most common questions. If yours isn't here, ask on the contact page."
)

# Verbatim from frontend/site/lib/design-copy.ts. Keep in sync when the design copy changes — a
# drift here only affects the placeholder the panel shows, never what the site renders.
SITE_COPY_DEFAULTS: dict[str, dict[Language, str]] = {
    "hero_eyebrow": {
        Language.fa: "کانفیگ رایگان روزانه",
        Language.en: "Free daily config",
    },
    "hero_h1_a": {
        Language.fa: "کانفیگ رایگان و پرسرعت،",
        Language.en: "Free, fast configs —",
    },
    "hero_h1_b": {
        Language.fa: "در چند ثانیه",
        Language.en: "in seconds",
    },
    "hero_sub": {Language.fa: _HERO_SUB_FA, Language.en: _HERO_SUB_EN},
    "trust1": {Language.fa: "بدون ثبت‌نام", Language.en: "No signup"},
    "trust2": {Language.fa: "همیشه رایگان", Language.en: "Free forever"},
    "trust3": {Language.fa: "هر ۲۴ ساعت تازه", Language.en: "Fresh every 24h"},
    "trust4": {Language.fa: "+۱۲٬۰۰۰ کاربر", Language.en: "12,000+ users"},
    "w_title": {Language.fa: "کانفیگ رایگان امروز", Language.en: "Today's free config"},
    "w_sub": {
        Language.fa: "یک لوکیشن انتخاب کن و بگیر",
        Language.en: "Pick a location and claim",
    },
    "cta_get": {Language.fa: "دریافت کانفیگ", Language.en: "Get config"},
    "m_title": {
        Language.fa: "حجم بیشتری می‌خواهی؟",
        Language.en: "Want more daily volume?",
    },
    "loc_eyebrow": {Language.fa: "لوکیشن‌ها", Language.en: "Locations"},
    "loc_title": {
        Language.fa: "از هر کشوری که بخواهی",
        Language.en: "From any country you like",
    },
    "loc_sub": {
        Language.fa: "کانفیگ اوکراین، آلمان، آمریکا و بیشتر — همه رایگان و روزانه.",
        Language.en: "Ukraine, Germany, USA and more — all free, every day.",
    },
    "app_eyebrow": {Language.fa: "اپ‌های سازگار", Language.en: "Compatible apps"},
    "app_title": {
        Language.fa: "در اپ دلخواهت باز کن",
        Language.en: "Open in your favorite app",
    },
    "app_sub": {
        Language.fa: "کانفیگ با همهٔ کلاینت‌های محبوب کار می‌کند. اپِ متناسب با دستگاهت را انتخاب کن.",
        Language.en: "Configs work with every popular client. Pick the app that fits your device.",
    },
    "faq_eyebrow": {Language.fa: "سوالات متداول", Language.en: "FAQ"},
    "faq_title": {Language.fa: "سوالی داری؟", Language.en: "Got a question?"},
    "faq_sub": {Language.fa: _FAQ_SUB_FA, Language.en: _FAQ_SUB_EN},
}


def content_key(design_key: str) -> str:
    """``hero_sub`` → ``site_copy_hero_sub`` (the row name in the ``content`` table)."""
    return f"{SITE_COPY_PREFIX}{design_key}"


def design_key(content_key_: str) -> str | None:
    """The inverse. ``None`` when the row isn't a design-copy override."""
    if not content_key_.startswith(SITE_COPY_PREFIX):
        return None
    return content_key_[len(SITE_COPY_PREFIX) :]


def default_for(design_key_: str, lang: Language) -> str:
    return SITE_COPY_DEFAULTS.get(design_key_, {}).get(lang, "")
