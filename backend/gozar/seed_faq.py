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
        # No hour count: the window is the site_trial_hours setting, and a number frozen into
        # seeded copy goes stale the day an operator changes it.
        "answer": (
            "هر بار که زمان کانفیگت تمام شود، یک کانفیگ رایگان تازه می‌گیری؛ لوکیشن را انتخاب کن،"
            " دکمه را بزن و لینک را در اپت وارد کن."
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
        "answer": (
            "با دعوت دوستان، نصب وب‌اپ و روشن‌کردن اعلان‌ها؛ هر کدام حجم روزانه‌ات را بیشتر می‌کند."
        ),
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
    # Phase E (C-36): questions support kept answering by hand. A running install gets them from
    # migration 5b7e2c9d4a61 — this seed runs once (the seeded_site_faq marker).
    {
        "locale": "fa",
        "category": "trouble",
        "question": "یک لوکیشن وصل نمی‌شود؛ باید تا کانفیگ بعدی صبر کنم؟",
        "answer": (
            "نه. تا وقتی کانفیگت فعال است، از صفحهٔ «کانفیگ من» می‌توانی لوکیشن دیگری "
            "انتخاب کنی. لینک تازهٔ همان لوکیشن را در اپت وارد کن؛ حجم و زمان کانفیگ همان "
            "قبلی است."
        ),
        "position": 8,
    },
    {
        "locale": "fa",
        "category": "trouble",
        "question": "روی اینترنت همراه هم کار می‌کند؟",
        "answer": (
            "بله؛ کانفیگ به نوع اینترنت بستگی ندارد و روی وای‌فای و اینترنت همراه هر دو "
            "قابل استفاده است. اختلال‌ها ولی بین اپراتورها فرق دارد؛ اگر روی یکی وصل نشد، "
            "لوکیشن دیگری را امتحان کن."
        ),
        "position": 9,
    },
    {
        "locale": "fa",
        "category": "start",
        "question": "چه اطلاعاتی از من نگه داشته می‌شود؟",
        "answer": (
            "برای دریافت کانفیگ نام، ایمیل یا شماره نمی‌گیریم. این مرورگر با یک کوکی "
            "امضاشده شناخته می‌شود؛ یک اثر انگشت سبک مرورگر و هشی از محدودهٔ شبکه‌ات (نه "
            "خود IP) هم فقط برای جلوگیری از سوءاستفاده نگه داشته می‌شود، و حجم مصرفی "
            "کانفیگت برای سقف روزانه شمرده می‌شود. جزئیات در صفحهٔ حریم خصوصی است."
        ),
        "position": 10,
    },
    {
        "locale": "fa",
        "category": "trouble",
        "question": "اگر سایت باز نشد، کانفیگم هم قطع می‌شود؟",
        "answer": (
            "نه. کانفیگی که در اپت وارد کرده‌ای به این سایت وابسته نیست و تا پایان زمانش "
            "کار می‌کند. اگر قبلاً در همین مرورگر کانفیگ گرفته‌ای، آخرین لینکش برای صفحهٔ "
            "آفلاین سایت هم نگه داشته می‌شود."
        ),
        "position": 11,
    },
    {
        "locale": "en",
        "category": "start",
        "question": "How does the free config work?",
        "answer": (
            "Each time your config's time runs out you can claim a fresh free one; pick a location,"
            " press the button and import the link into your app."
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
            "By inviting friends, installing the web app and enabling notifications — each one"
            " adds to your daily volume."
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
    {
        "locale": "en",
        "category": "trouble",
        "question": "A location won't connect — do I have to wait for my next config?",
        "answer": (
            "No. While your config is active you can pick another location on the “My "
            "config” page. Import that location's new link into your app — your volume and "
            "time stay the same."
        ),
        "position": 8,
    },
    {
        "locale": "en",
        "category": "trouble",
        "question": "Does it work on mobile data?",
        "answer": (
            "Yes — the config doesn't depend on the kind of connection, so it works on "
            "Wi-Fi and mobile data alike. Disruptions differ between carriers, though: if "
            "it won't connect on one, try another location."
        ),
        "position": 9,
    },
    {
        "locale": "en",
        "category": "start",
        "question": "What do you keep about me?",
        "answer": (
            "We take no name, email or phone number to claim a config. This browser is "
            "recognised by a signed cookie; a light browser fingerprint and a hash of your "
            "network range (not the IP itself) are kept only to prevent abuse, and your "
            "config's usage is counted for the daily cap. The details are on the Privacy "
            "page."
        ),
        "position": 10,
    },
    {
        "locale": "en",
        "category": "trouble",
        "question": "If the site won't open, does my config stop working?",
        "answer": (
            "No. A config you've imported into your app doesn't depend on this site and "
            "keeps working until its time is up. If you've claimed one in this browser "
            "before, its last link is kept for the site's offline page too."
        ),
        "position": 11,
    },
)
