"""Default FAQ items, seeded into ``site_faq_items`` on boot (idempotent).

These are the SAME questions and answers the public site ships in-code
(``frontend/site/lib/content.ts`` → ``FAQ_ITEMS``), which the site still uses as its offline
fallback. Seeding them means the panel opens showing exactly what visitors see — an empty table
that quietly replaced the built-in list would make adding one question look like deleting eight.

``add_default`` keys on (locale, question), so re-running the seeder never duplicates a row and
never overwrites one the operator edited.

Kept out of ``seed.py`` for the same reason the landings are: bulk copy would drown the
settings/content defaults that file exists to show.
"""

from __future__ import annotations

# `position` is the index within its locale — the order the site renders them in.
DEFAULT_SITE_FAQ: tuple[dict[str, str | int], ...] = (
    {
        "locale": "fa",
        "category": "start",
        "question": "کانفیگ رایگان چطور کار می‌کند؟",
        "answer": (
            "هر ۲۴ ساعت یک کانفیگ رایگان می‌گیری؛ لوکیشن را انتخاب کن، دکمه را بزن و لینک را در"
            " اپت وارد کن."
        ),
        "position": 0,
    },
    {
        "locale": "fa",
        "category": "start",
        "question": "برای دریافت باید ثبت‌نام کنم؟",
        "answer": "نه. دریافت کاملاً بدون ثبت‌نام است و هیچ ایمیل یا شماره‌ای نمی‌خواهد.",
        "position": 1,
    },
    {
        "locale": "fa",
        "category": "vol",
        "question": "چطور حجم روزانه‌ام را بیشتر کنم؟",
        "answer": "با دعوت دوستان، نصب وب‌اپ و روشن‌کردن اعلان‌ها — از بخش «حجم بیشتر».",
        "position": 2,
    },
    {
        "locale": "fa",
        "category": "vol",
        "question": "اگر حجم امروزم تمام شود؟",
        "answer": "با یک دعوت موفق، همان کانفیگ همان لحظه دوباره فعال می‌شود.",
        "position": 3,
    },
    {
        "locale": "fa",
        "category": "apps",
        "question": "با چه اپ‌هایی کار می‌کند؟",
        "answer": "v2rayNG (اندروید)، Streisand (آیفون/مک) و Happ (همهٔ دستگاه‌ها).",
        "position": 4,
    },
    {
        "locale": "fa",
        "category": "apps",
        "question": "روی ویندوز نصب می‌شود؟",
        "answer": "بله، با کلاینت Happ ویندوز.",
        "position": 5,
    },
    {
        "locale": "fa",
        "category": "trouble",
        "question": "وصل نمی‌شوم",
        "answer": "کانفیگ را دوباره بگیر، زمان دستگاه را چک کن و لوکیشن دیگری را امتحان کن.",
        "position": 6,
    },
    {
        "locale": "fa",
        "category": "trouble",
        "question": "سرعت کم است",
        "answer": "لوکیشن نزدیک‌تر را انتخاب کن و مطمئن شو حجم روزانه‌ات تمام نشده.",
        "position": 7,
    },
    {
        "locale": "en",
        "category": "start",
        "question": "How does the free config work?",
        "answer": (
            "Every 24 hours you get a free config; pick a location, press the button and import"
            " the link into your app."
        ),
        "position": 0,
    },
    {
        "locale": "en",
        "category": "start",
        "question": "Do I need to sign up?",
        "answer": "No. Claiming is entirely signup-free and needs no email or phone number.",
        "position": 1,
    },
    {
        "locale": "en",
        "category": "vol",
        "question": "How do I grow my daily volume?",
        "answer": (
            "By inviting friends, installing the web app and enabling notifications — from the"
            " 'More volume' section."
        ),
        "position": 2,
    },
    {
        "locale": "en",
        "category": "vol",
        "question": "What if today's volume runs out?",
        "answer": "One successful invite revives the same config instantly.",
        "position": 3,
    },
    {
        "locale": "en",
        "category": "apps",
        "question": "Which apps does it work with?",
        "answer": "v2rayNG (Android), Streisand (iOS/macOS) and Happ (all devices).",
        "position": 4,
    },
    {
        "locale": "en",
        "category": "apps",
        "question": "Can I install it on Windows?",
        "answer": "Yes, with the Happ Windows client.",
        "position": 5,
    },
    {
        "locale": "en",
        "category": "trouble",
        "question": "I can't connect",
        "answer": "Re-claim the config, check your device clock and try a different location.",
        "position": 6,
    },
    {
        "locale": "en",
        "category": "trouble",
        "question": "It's slow",
        "answer": "Pick a closer location and make sure your daily volume isn't used up.",
        "position": 7,
    },
)
