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
    # Not hero_h1_a / hero_h1_b / hero_sub: the page draws its title and subtitle from the seeded
    # site_hero_title / site_hero_sub rows whenever they are set — and they always are — so those
    # three were fields whose edits never reached the page. One editable field per text.
    "hero": [
        "hero_eyebrow",
        "hero_sub_short",
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
    # The /about page's prose. Its "how it stays free" paragraph is deliberately neutral in code —
    # what funds the service is the operator's to say, and this is where they say it.
    "about": ["about_lead", "about_body", "about_free_body", "about_privacy_body"],
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
_ABOUT_BODY_FA = (
    "هدف ما ساده است: دسترسی آزاد و بی‌دردسر، بدون ثبت‌نام و بدون هزینه. تیم کوچک ما روی سرعت،"
    " پایداری و حریم خصوصی تمرکز دارد."
)
_ABOUT_BODY_EN = (
    "Our goal is simple: open, hassle-free access with no signup and no cost. Our small team"
    " focuses on speed, stability and privacy."
)
_ABOUT_FREE_FA = (
    "دریافت کانفیگ هیچ پرداختی نمی‌خواهد و هیچ مرحلهٔ پولی ندارد. هر کانفیگ آزمایشی است: مدت و"
    " حجم روزانهٔ مشخصی دارد و وقتی تمام شد، کانفیگ تازه می‌گیری. حجم بیشتر را هم با دعوت دوستان و"
    " ماموریت‌های سایت می‌گیری، نه با پرداخت."
)
_ABOUT_FREE_EN = (
    "Claiming a config costs nothing and has no paid step. Every config is a trial with a set"
    " length and a set daily volume; when it ends, you claim a fresh one. More volume comes from"
    " inviting friends and the site's missions, not from paying."
)
_ABOUT_PRIVACY_FA = (
    "برای دریافت کانفیگ نام، ایمیل یا شماره نمی‌خواهیم. این مرورگر با یک کوکی امضاشده شناخته"
    " می‌شود. یک اثر انگشت سبک مرورگر و یک هش نمک‌دار از محدودهٔ شبکه‌ات (نه خود IP) هم فقط برای"
    " جلوگیری از سوءاستفاده نگه داشته می‌شود، و حجم مصرفی کانفیگت شمرده می‌شود تا سقف روزانه اعمال"
    " شود."
)
_ABOUT_PRIVACY_EN = (
    "We don't ask for a name, email or phone number to claim a config. This browser is recognised"
    " by a signed cookie. A light browser fingerprint and a salted hash of your network range (not"
    " the IP itself) are kept only to prevent abuse, and your config's usage is counted so the"
    " daily cap can apply."
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
    # The phone hero's one-to-two-line subtitle (the long one pushed the claim button off-screen).
    "hero_sub_short": {
        Language.fa: "هر روز یک کانفیگ رایگان؛ بدون ثبت‌نام، با لوکیشن دلخواه.",
        Language.en: "A free config every day — no signup, any location you like.",
    },
    "trust1": {Language.fa: "بدون ثبت‌نام", Language.en: "No signup"},
    "trust2": {Language.fa: "همیشه رایگان", Language.en: "Free forever"},
    # `{h}` is filled with site_trial_hours and `{n}` with the real configs-delivered count (rounded
    # down to the thousand); the site hides the chip rather than print a guess when either value is
    # missing. An override may keep the token or drop it — both render.
    "trust3": {Language.fa: "هر {h} ساعت تازه", Language.en: "Fresh every {h}h"},
    "trust4": {Language.fa: "+{n} کانفیگ تحویل‌شده", Language.en: "{n}+ configs delivered"},
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
    # `{locs}` is filled with the squad's live locations in the visitor's language ("Germany,
    # Netherlands, Finland and more"): the old sentence named Ukraine, Germany and the USA whether
    # or not the squad served any of them. An override may keep the token or drop it — both render.
    "loc_sub": {
        Language.fa: "کانفیگ {locs} — همه رایگان و روزانه.",
        Language.en: "{locs} — all free, every day.",
    },
    "app_eyebrow": {Language.fa: "اپ‌های سازگار", Language.en: "Compatible apps"},
    "app_title": {
        Language.fa: "با اپ دلخواهت وصل شو",
        Language.en: "Connect with your favorite app",
    },
    # The apps the site actually links and deep-links — "every popular client" was a promise
    # about clients nobody had tried.
    "app_sub": {
        Language.fa: "کانفیگ در Happ، v2rayNG و Streisand کار می‌کند. راهنمای اپ دستگاهت را باز کن.",
        Language.en: (
            "The config works in Happ, v2rayNG and Streisand. Open the guide for your app."
        ),
    },
    "faq_eyebrow": {Language.fa: "سوالات متداول", Language.en: "FAQ"},
    "faq_title": {Language.fa: "سوالی داری؟", Language.en: "Got a question?"},
    "faq_sub": {Language.fa: _FAQ_SUB_FA, Language.en: _FAQ_SUB_EN},
    "about_lead": {
        Language.fa: "GozarX یک ابزار رایگان است که هر روز به همه یک کانفیگ آزمایشی می‌دهد.",
        Language.en: "GozarX is a free tool that hands everyone a trial config every day.",
    },
    "about_body": {Language.fa: _ABOUT_BODY_FA, Language.en: _ABOUT_BODY_EN},
    "about_free_body": {Language.fa: _ABOUT_FREE_FA, Language.en: _ABOUT_FREE_EN},
    "about_privacy_body": {Language.fa: _ABOUT_PRIVACY_FA, Language.en: _ABOUT_PRIVACY_EN},
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
