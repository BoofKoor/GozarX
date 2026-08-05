"""A stand-in admin API, so the panel can be RENDERED and looked at without a database.

Local-only, no dependencies. It serves the built SPA from `frontend/admin/dist` and answers every
admin endpoint the panel calls, with response shapes taken verbatim from the pydantic models — so
the pages exercise their real code paths, not a mock component tree.

    cd frontend/admin && npm run build
    python3 docs/panel/mockapi.py          # http://127.0.0.1:4174/admin/

Query parameters on the SPA shell:
  ?theme=light|dark   ?locale=fa|en       seeded into localStorage before the app module runs,
                                          which is the only way to set them in a headless browser
  ?fill=<name>        run one of FILLS below ~900ms after load — used to capture states that
                      need interaction (a hovered chart, a filled form, an open dialog)

Rendering it headless and reading the PNG back is the verification loop that catches what a test
cannot: bidi reordering, a Tailwind class that compiled to nothing, a colour that lost its
contrast. See docs/panel/README.md.
"""
import http.server, json, os, socketserver, urllib.parse, math, random
random.seed(7)
# Resolved from this file, so the server runs from any working directory.
DIST = os.environ.get(
    "PANEL_DIST",
    os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
                 "frontend", "admin", "dist"),
)

def days(n, base, amp, phase=0.0):
    out = []
    from datetime import date, timedelta
    today = date(2026, 8, 4)
    for i in range(n):
        d = today - timedelta(days=n - 1 - i)
        v = int(base + amp * math.sin(i / 3.0 + phase) + random.randint(-6, 10))
        out.append({"day": d.isoformat(), "count": max(0, v)})
    return out

def stats(n):
    return {
        "total_users": 8412, "available": 5103, "active": 1228, "banned": 61,
        "configs_today": 326, "referrals": 420, "range_days": n,
        "new_today": 136, "new_this_week": 381, "growth_pct": 12.4,
        "signups_in_range": 1180, "signups_prev_range": 1042, "signups_delta_pct": 13.2,
        "claims_in_range": 2841, "claims_prev_range": 2610, "claims_delta_pct": 8.8,
        "claimers_in_range": 1228, "claimers_prev_range": 1266, "claimers_delta_pct": -3.0,
        "online_now": 312, "online_squad_scoped": True, "online_last_day": 498,
        "online_last_week": 512, "never_online": 900, "panel_online": True,
        "panel_status_counts": {"ACTIVE": 1228, "EXPIRED": 300},
        "panel_total_users": 8412, "total_traffic_bytes": 3_375_000_000_000,
        "nodes_online": 4, "conversion_pct": 86.0, "reminder_enabled": 4102,
        "avg_referrals": 0.42,
        "claims_series": days(n, 210, 90),
        "signups_series": days(n, 150, 40, 1.2),
        "languages": [{"label": "fa", "count": 5240}, {"label": "en", "count": 2010},
                      {"label": "ru", "count": 1162}],
        "top_locations": [{"label": "Germany", "count": 1883}, {"label": "Netherlands", "count": 1502},
                          {"label": "Finland", "count": 1140}],
        "top_referrers": [{"telegram_id": 7314829, "referral_count": 420}],
    }

def analytics(n):
    heat = [{"dow": d, "hour": h,
             "count": int(40 + 55 * math.sin((h - 5) / 24 * math.pi)) if 6 <= h <= 23 else 5}
            for d in range(7) for h in range(24)]
    return {
        "range_days": n, "dau": 498, "wau": 1228, "mau": 3140, "stickiness_pct": 15.9,
        "median_hours_to_claim": {"value": 6.92, "previous": 7.85, "change_pct": -11.8},
        "activation_24h": {"value": 74.0, "previous": 71.2, "change_pct": 3.9},
        "first_claimers_in_range": 1180, "claimers_all_time": 7231,
        # `eligible` is the users who COULD have been referred, not every user — see the route.
        "referral": {"joined": 3449, "joined_claimed": 2610,
                     "invitee_conversion_pct": 75.7, "k_factor": 0.42,
                     "eligible": 20288, "joined_share_pct": 17.0},
        "referral_cap": {"limit": 10, "at_cap": 210, "with_referrals": 1840},
        "heatmap": heat, "signup_heatmap": heat,
        "claims_distribution": {"1": 2100, "2-3": 3010, "4-6": 1420, "7+": 701},
        "reminder_by_language": [{"label": "fa", "on": 3200, "off": 2040}],
        "active_users_series": days(n, 480, 60),
        "new_vs_returning": [{"day": p["day"], "new": p["count"] // 3,
                              "returning": p["count"]} for p in days(n, 300, 70)],
    }

RETENTION = {"weeks": 8, "cohorts": [
    {"week": "2026-06-01", "size": 420, "retention": [100.0, 63.0, 41.0, 28.0]},
    {"week": "2026-06-08", "size": 511, "retention": [100.0, 61.5, 39.0]},
    {"week": "2026-06-15", "size": 388, "retention": [100.0, 64.5]},
]}

HEALTH = {
    "status": "ok", "generated_at": "2026-08-04T18:00:00Z",
    "db": {"ok": True, "latency_ms": 3.2, "detail": None},
    "redis": {"ok": True, "latency_ms": 1.1, "detail": None},
    "panel": {"ok": True, "latency_ms": 124.0, "detail": None},
    "telegram": {"ok": True, "latency_ms": 88.0, "detail": None},
    "webhook": {"configured": True, "url_set": True, "pending": 0,
                "recent_error": False, "last_error_at": None, "last_error": None},
    "host": {"load1": 0.4, "load5": 0.5, "load15": 0.6, "cpu_count": 4,
             "mem_total": 8e9, "mem_used": 3e9, "mem_pct": 37.5,
             "disk_total": 8e10, "disk_used": 2e10, "disk_pct": 25.0, "uptime_s": 998877},
    "panel_stats": None,
}

LANG_POP = {"fa": 5240, "en": 2010, "ru": 1162}
CLAIM_LOCATIONS = ["Finland", "France", "Germany", "Netherlands", "Sweden"]
NAMES = ["gozar_7f3a", "gozar_91be", "gozar_c4d2", "gozar_5a10", "gozar_ee77",
         "gozar_2b93", "gozar_84fc", "gozar_16d5", None, "gozar_a0b1"]
STATUSES = ["available", "active_config", "banned", "available", "active_config"]

def users_page(page, size, status, search, location=None):
    rows = []
    for i in range(200):
        rows.append({
            "telegram_id": 5_000_000_000 + i * 137_951,
            "status": STATUSES[i % len(STATUSES)],
            "language": ["fa", "en", "ru"][i % 3],
            "referral_count": (i * 7) % 41,
            "panel_username": NAMES[i % len(NAMES)],
            "reminder_enabled": i % 3 != 0,
            "referred_by": 5_000_000_000 if i % 4 == 0 else None,
            "created_at": f"2026-0{1 + i % 7}-{1 + i % 27:02d}T09:{i % 60:02d}:00Z",
            "configs": (i * 3) % 19,
            # Every fifth user has never claimed, so the column has a real "—" in it.
            "last_location": None if i % 5 == 4 else CLAIM_LOCATIONS[i % len(CLAIM_LOCATIONS)],
            # Same rule as last_location: a user who never claimed has no last claim either, so
            # the recency column shows a real "—" rather than an invented date.
            "last_claim_at": None if i % 5 == 4 else
                f"2026-08-0{1 + i % 4}T{(6 + i) % 24:02d}:{i % 60:02d}:00Z",
        })
    if status:
        rows = [r for r in rows if r["status"] == status]
    if search:
        rows = [r for r in rows if search in str(r["telegram_id"])
                or (r["panel_username"] or "").find(search) >= 0]
    if location:
        rows = [r for r in rows if r["last_location"] == location]
    start = (page - 1) * size
    return {"items": rows[start:start + size], "total": len(rows),
            "page": page, "page_size": size}



def usage(days):
    """The usage tab's payload, with a counter reset planted on one day so the warning path is
    reachable from a screenshot rather than only from a unit test."""
    from datetime import date, timedelta
    today = date(2026, 8, 4)
    GB = 1024 ** 3
    daily = []
    for i in range(days):
        day = today - timedelta(days=days - 1 - i)
        reset = i == days - 4
        peak = int(240 + 90 * math.sin(i / 2.7) + (i % 5) * 12)
        daily.append({
            "day": day.isoformat(),
            "bytes": 0 if reset else int((820 + 260 * math.sin(i / 3.1) + (i % 4) * 45) * GB / 10),
            "peak_online": peak,
            "avg_online": int(peak * 0.62),
            "counter_reset": reset,
        })
    total = sum(d["bytes"] for d in daily)
    prev = int(total * 0.88)
    peak_now = max(d["peak_online"] for d in daily)
    return {
        "range_days": days,
        "recording_since": "2026-05-02T00:30:00Z",
        "samples": days * 24,
        "traffic": {"value": total, "previous": prev,
                    "change_pct": round((total - prev) / prev * 100, 1)},
        "peak_online": {"value": peak_now, "previous": 302, "change_pct": 9.6},
        "bytes_per_user": {"value": total / 1228, "previous": prev / 1180,
                           "change_pct": 6.4},
        "nodes_online": 3,
        "mem_used": 5_100_000_000,
        "mem_total": 8_000_000_000,
        "daily": daily,
    }


def user_detail(uid):
    """The record dialog's payload — same shape as UserDetailOut."""
    from datetime import date, timedelta
    today = date(2026, 8, 4)
    return {
        "telegram_id": uid, "status": "active_config", "language": "fa",
        "referral_count": 27, "panel_username": "gozar_7f3a", "reminder_enabled": True,
        "referred_by": 5_000_000_000, "created_at": "2026-03-14T09:20:00Z", "configs": 11,
        "last_location": "Germany", "last_claim_at": "2026-08-04T18:20:00Z",
        "claims_series": [
            {"day": (today - timedelta(days=29 - i)).isoformat(),
             "count": max(0, int(2 + 2 * math.sin(i / 3.0)) + (i % 3 == 0))}
            for i in range(30)
        ],
        "recent_claims": [
            {"location": "Finland", "created_at": "2026-08-04T16:10:00Z"},
            {"location": "Germany", "created_at": "2026-08-03T19:40:00Z"},
            {"location": "Germany", "created_at": "2026-08-02T20:05:00Z"},
            {"location": "Netherlands", "created_at": "2026-07-31T18:20:00Z"},
        ],
        "traffic_bytes": 9_400_000_000,
    }


TEXT_KEYS = [
    ("welcome", ["name"]), ("help", []), ("main_menu", []), ("choose_language", []),
    ("choose_location", ["count"]), ("config_delivered", ["location", "expire"]),
    ("config_active", ["expire"]), ("config_limited", []), ("config_size", ["size"]),
    ("already_claimed", ["hours"]), ("no_locations", []), ("not_ready", []), ("panel_error", []),
    ("banned", []), ("invite", ["link", "reward"]), ("referral_joined", ["reward"]),
    ("status", []), ("status_received", []), ("status_not_received", []), ("status_usage", ["used"]),
    ("settings_menu", []), ("reminder_enabled", []), ("reminder_disabled", []),
    ("reminder_expired", []), ("reminder_limited", []), ("required_apps", []), ("ads", []),
    ("admin_menu", []), ("admin_stats", []), ("admin_broadcast_prompt", []),
    ("admin_forward_prompt", []), ("admin_user_prompt", []), ("admin_user_card", ["id"]),
    ("admin_user_not_found", []), ("admin_ban_confirm", []), ("admin_ban_done", []),
    ("admin_unban_done", []), ("admin_reclaim_done", []), ("admin_zero_confirm", []),
    ("admin_zero_done", []), ("admin_send_preview", []), ("admin_send_queued", ["n"]),
    ("admin_send_failed", []), ("admin_send_cancelled", []), ("admin_refresh_done", []),
    ("admin_refresh_failed", []), ("admin_reset_all_confirm", []), ("admin_reset_all_queued", []),
    ("site_hero_title", []), ("site_hero_sub", []), ("site_meta_title", []),
    ("site_meta_description", []), ("site_push_expired_title", []), ("site_push_expired_body", []),
    ("site_push_limited_title", []), ("site_push_limited_body", []),
]
_FA_BODY = ("سلام {name}! خوش آمدید "
            "به گذرX — هر روز یک "
            "کانفیگ رایگان.")
TEXTS = [
    {"key": k, "fa": _FA_BODY if "{name}" not in _FA_BODY or i == 0 else _FA_BODY.split("!")[1],
     "en": "" if i % 4 == 3 else "Welcome to GozarX — one free config a day.",
     "ru": "" if i % 3 else "Добро пожаловать!",
     "placeholders": ph, "link_preview": i % 5 == 0}
    for i, (k, ph) in enumerate(TEXT_KEYS)
]

_SCREENS = [
    ("main_menu", [("get_config", "دریافت کانفیگ", "Get config", 0, 0, False),
                   ("status", "وضعیت", "Status", 1, 0, False),
                   ("invite", "دعوت دوستان", "Invite friends", 1, 1, False),
                   ("help", "راهنما", "Help", 2, 0, False),
                   ("settings", "تنظیمات", "Settings", 2, 1, False)]),
    ("location", [("loc_prev", "‹", "‹", 0, 0, True),
                  ("loc_next", "›", "›", 0, 1, True),
                  ("loc_back", "بازگشت", "Back", 1, 0, True)]),
    ("config_delivered", [("change_loc", "تغییر لوکیشن", "Change location", 0, 0, False),
                          ("ad", "کانال ما", "Our channel", 0, 1, False),
                          ("back", "بازگشت", "Back", 1, 0, True)]),
]
BUTTONS = [
    {"key": key, "screen": screen, "is_critical": crit, "is_visible": key != "ad",
     "default_row": row, "default_position": pos, "effective_row": row, "effective_position": pos,
     "default_label": {"fa": fa, "en": en, "ru": en},
     "effective_label": {"fa": fa, "en": en, "ru": en},
     "style": "primary" if key == "get_config" else None, "customized": key == "get_config"}
    for screen, items in _SCREENS
    for (key, fa, en, row, pos, crit) in items
]

BOT_SETTINGS = {
    "trial_squad": "sq-1", "locations": ["Germany", "Netherlands"],
    "daily_limit_mb": 1024, "referral_reward_mb": 500, "referral_reward_limit": 10,
    "trial_hours": 24, "ads_enabled": True, "configs_per_page": 8,
    "ad_button_enabled": True, "ad_button_text": "کانال ما",
    "ad_button_url": "https://t.me/gozarx", "ad_button_emoji_id": "5368324170671202286",
}
SQUAD_LOCATIONS = ["Germany", "Netherlands", "Finland", "France", "Sweden"]


def history(minutes):
    from datetime import datetime, timedelta, timezone
    end = datetime(2026, 8, 4, 18, 0, tzinfo=timezone.utc)
    step = max(1, minutes // 60)
    return [
        {"ts": (end - timedelta(minutes=minutes - i * step)).isoformat(),
         "api_ms": None if i % 17 == 5 else int(70 + 40 * math.sin(i / 4)) + random.randint(0, 25),
         "pending": max(0, int(6 + 5 * math.sin(i / 3)) + random.randint(-3, 4))}
        for i in range(minutes // step)
    ]



SITE_SETTINGS = {
    "trial_squad": "sq-1", "locations": ["Germany", "Finland"], "popular_location": "Germany",
    "trial_hours": 24, "daily_limit_mb": 1024, "referral_reward_mb": 300,
    "referral_reward_limit": 10, "reward_pwa_mb": 200, "reward_push_mb": 150,
    "reward_streak_mb": 250, "streak_days": 3,
}
SITE_STATS = {
    "range_days": 14,
    "visitors": {"value": 4210, "previous": 3880, "change_pct": 8.5},
    "new_visitors": {"value": 2905, "previous": 2740, "change_pct": 6.0},
    "returning_visitors": {"value": 1305, "previous": 1140, "change_pct": 14.5},
    "claimers": {"value": 1782, "previous": 1690, "change_pct": 5.4},
    "conversion_pct": 42.3, "conversion_pct_prev": 43.6,
    "active_configs_live": 604, "active_configs_stale": 37, "claims_today": 168,
    "total_devices_all_time": 30144, "devices_claimed_all_time": 9820,
    "conversion_all_time_pct": 32.6, "push_subscribers": 1490, "location_changes": 212,
    "visitors_series": days(14, 300, 60), "claims_series": days(14, 130, 40, 0.8),
    "top_locations": [{"label": "Germany", "count": 903}, {"label": "Finland", "count": 611},
                      {"label": "Netherlands", "count": 402}],
    "locations_total": 5,
    "status_counts": {"available": 5100, "active_config": 604, "blocked": 22},
}
SITE_ANALYTICS = {
    "range_days": 14, "dau": 402, "wau": 1180, "mau": 2960, "stickiness_pct": 13.6,
    "visitors_24h": 690, "visitors_7d": 2310, "visitors_30d": 5120,
    "visit_stickiness_pct": 13.5, "claims_in_range": 2210, "devices_active_in_range": 1782,
    "reward_economy": [{"type": "pwa", "grants": 810, "total_mb": 162000},
                       {"type": "push", "grants": 1490, "total_mb": 223500}],
    "streak_distribution": {"0": 3900, "1-2": 1100, "3-6": 480, "7+": 190},
    "active_streaks": 670,
    "push": {"active": 1490, "inactive": 310,
             "by_locale": [{"label": "fa", "count": 1120}, {"label": "en", "count": 370}]},
    "abuse": {"shared_fingerprint_devices": 46,
              "top_ip_buckets": [{"label": "185.23.44.x", "count": 9},
                                 {"label": "91.99.7.x", "count": 6}]},
}
BROADCAST_DRAFTS = [
    {"id": 2, "title": "یادآوری: سقف پاداش دعوت", "body": "یادآوری: سقف پاداش دعوت …",
     "languages": "fa", "only_active": False, "only_referrers": True,
     "buttons": [{"text": "کانال ما", "url": "https://t.me/gozarx_channel"}],
     "send_hour": 21, "updated_at": "2026-08-04T19:05:00Z"},
    {"id": 1, "title": "نگهداری برنامه‌ریزی‌شده — شنبه", "body": "نگهداری برنامه‌ریزی‌شده …",
     "languages": "", "only_active": False, "only_referrers": False,
     "buttons": [], "send_hour": None, "updated_at": "2026-08-02T11:40:00Z"},
]

BROADCAST_HISTORY = [
    {"id": 4, "body": "دو لوکیشن تازه اضافه شد — فنلاند و ترکیه.", "languages": "fa",
     "only_active": False, "only_referrers": False,
     "buttons": [{"text": "کانال ما", "url": "https://t.me/gozarx"}],
     "status": "done", "recipients": 8412, "sent": 8298, "failed": 41, "removed": 73,
     "scheduled_for": None, "created_at": "2026-08-02T18:00:00Z",
     "finished_at": "2026-08-02T18:05:00Z"},
    {"id": 3, "body": "یادآوری: سقف پاداش دعوت", "languages": "", "only_active": False,
     "only_referrers": True, "buttons": None, "status": "sending", "recipients": 2355,
     "sent": 1140, "failed": 12, "removed": 21, "scheduled_for": None,
     "created_at": "2026-08-04T17:30:00Z", "finished_at": None},
    {"id": 2, "body": "قطعی کوتاه پنل — عذرخواهی", "languages": "fa,en", "only_active": True,
     "only_referrers": False, "buttons": None, "status": "done", "recipients": 3045,
     "sent": 2904, "failed": 45, "removed": 96, "scheduled_for": None,
     "created_at": "2026-07-26T12:00:00Z", "finished_at": "2026-07-26T12:03:00Z"},
    {"id": 1, "body": "به‌روزرسانی شرایط استفاده", "languages": "", "only_active": False,
     "only_referrers": False, "buttons": None, "status": "failed", "recipients": 8390,
     "sent": 0, "failed": 0, "removed": 0, "scheduled_for": None,
     "created_at": "2026-07-21T09:00:00Z", "finished_at": "2026-07-21T09:00:10Z"},
]
SITE_PUSH_HISTORY = [
    {"id": 3, "title": "سرور تازه اضافه شد", "body": "…", "url": "/status", "locale": "fa",
     "recipients": 1120, "sent": 1041, "failed": 44, "pruned": 35, "status": "done",
     "created_at": "2026-08-03T12:00:00Z", "finished_at": "2026-08-03T12:04:00Z"},
    {"id": 2, "title": "Maintenance tonight", "body": "…", "url": None, "locale": "en",
     "recipients": 370, "sent": 0, "failed": 0, "pruned": 0, "status": "sending",
     "created_at": "2026-08-04T09:00:00Z", "finished_at": None},
]
SITE_DEVICES = {
    "items": [
        {"uuid": f"d-{i:04d}", "handle": f"GZ-{7000+i:04X}",
         "status": ["available", "active_config", "blocked"][i % 3],
         "claims": (i * 3) % 17, "referral_count": (i * 5) % 12, "invited": (i * 7) % 19,
         "streak_count": i % 9, "has_fingerprint": i % 2 == 0,
         "ip_bucket": f"185.23.{40 + i % 5}.x",
         "site_panel_username": f"site_{i:04d}" if i % 4 else None,
         "last_claim_at": "2026-08-03T10:00:00Z" if i % 3 else None,
         "created_at": f"2026-0{1 + i % 7}-1{i % 9}T08:00:00Z"}
        for i in range(60)
    ],
    "total": 60, "page": 1, "page_size": 25,
}
SITE_COPY = [
    {"key": "hero_h1_a", "group": "hero", "fa": "اینترنت آزاد،", "en": "",
     "default_fa": "اینترنت آزاد،", "default_en": "Free internet,", "overridden": True},
    {"key": "hero_sub", "group": "hero", "fa": "", "en": "",
     "default_fa": "هر روز یک کانفیگ رایگان.", "default_en": "One free config a day.",
     "overridden": False},
    {"key": "site_meta_title", "group": "seo", "fa": "", "en": "",
     "default_fa": "گذرX — کانفیگ رایگان روزانه", "default_en": "GozarX — a free daily config",
     "overridden": False},
    {"key": "cta_get", "group": "widget", "fa": "", "en": "",
     "default_fa": "دریافت کانفیگ", "default_en": "Get a config", "overridden": False},
]
SITE_FAQ = [
    {"id": i, "locale": "fa", "category": ["start", "vol", "apps", "trouble"][i % 4],
     "question": f"سوال شمارهٔ {i}؟", "answer": "پاسخ نمونه برای این سوال.",
     "position": i, "published": i % 5 != 0}
    for i in range(1, 9)
]
SITE_PAGES = [
    {"id": i, "slug": f"landing-{i}", "locale": "fa" if i % 2 else "en",
     "title": f"Landing page {i}", "meta_description": "A sample landing page.",
     "heading": None, "body": "<p>Hello</p>", "location_remark": None,
     "published": i % 3 != 0, "created_at": "2026-07-01T00:00:00Z",
     "updated_at": "2026-08-01T00:00:00Z"}
    for i in range(1, 6)
]
SITE_MESSAGES = {
    "items": [
        {"id": i, "subject": f"موضوع پیام {i}", "body": "متن پیام نمونه از فرم تماس سایت.",
         "locale": "fa" if i % 2 else "en", "reply_handle": "user@example.com" if i % 2 else "@someone",
         "device_uuid": f"d-{i:04d}" if i % 3 else None, "read": i % 2 == 0,
         "created_at": "2026-08-02T11:00:00Z"}
        for i in range(1, 7)
    ],
    "total": 6, "matching": 6, "page": 1, "page_size": 20, "unread": 3,
}

# Snippets the shell can run once the app has mounted, to reach a state a screenshot needs.
_SET = ("var s=Object.getOwnPropertyDescriptor(el.constructor.prototype,'value').set;"
        "s.call(el,v);el.dispatchEvent(new Event('input',{bubbles:true}));")
FILLS = {
    # Hover the activity trend a third of the way in, so the crosshair + readout are captured.
    "trendtip": (
        "var svgs=[].slice.call(document.querySelectorAll('svg[role=img]'));"
        "var el=svgs.filter(function(s){return s.viewBox.baseVal.width===900})[0];"
        "if(!el){console.error('no AreaTrend svg');}else{"
        "var r=el.getBoundingClientRect();"
        "el.dispatchEvent(new PointerEvent('pointermove',{bubbles:true,"
        "clientX:r.left+r.width*0.62,clientY:r.top+r.height*0.4}));}"
    ),
    "broadcast": (
        "var el=document.querySelector('textarea');var v="
        "'\\u0633\\u0644\\u0627\\u0645 \\ud83d\\udc4b\\n\\n"
        "\\u0633\\u0631\\u0648\\u0631 \\u062a\\u0627\\u0632\\u0647\\u200c\\u06cc "
        "*\\u0641\\u0646\\u0644\\u0627\\u0646\\u062f* \\u0628\\u0647 \\u06af\\u0630\\u0631X "
        "\\u0627\\u0636\\u0627\\u0641\\u0647 \\u0634\\u062f \\u2014 \\u0627\\u0632 \\u0647\\u0645\\u06cc\\u0646 "
        "\\u0627\\u0645\\u0631\\u0648\\u0632 \\u0645\\u06cc\\u200c\\u062a\\u0648\\u0627\\u0646\\u06cc\\u062f "
        "\\u06a9\\u0627\\u0646\\u0641\\u06cc\\u06af \\u0631\\u0648\\u0632\\u0627\\u0646\\u0647\\u200c\\u062a\\u0627\\u0646 "
        "\\u0631\\u0627 \\u0627\\u0632 \\u0622\\u0646 \\u0628\\u06af\\u06cc\\u0631\\u06cc\\u062f.\\n\\n"
        "\\u0628\\u0631\\u0627\\u06cc \\u062f\\u0631\\u06cc\\u0627\\u0641\\u062a\\u060c "
        "/start \\u0631\\u0627 \\u0628\\u0632\\u0646\\u06cc\\u062f.';" + _SET
    ),
    "broadcast-en": (
        "var el=document.querySelector('textarea');var v='Hi \\ud83d\\udc4b\\n\\nA new "
        "*Finland* server just joined GozarX \\u2014 you can pull today\\u2019s config from it "
        "right now.\\n\\nTap /start to grab one.';" + _SET
    ),
    "user": "document.querySelectorAll('tbody tr')[1].click()",
    "text": "document.querySelectorAll('ul button')[0].click()",
    # The usage tab is the 5th of seven; reaching it needs a click, and a screenshot of the
    # dashboard's default tab proves nothing about it.
    "usage": "document.querySelectorAll('[role=tab]')[4].click()",
    "broadcast-partial": "document.querySelectorAll('button[aria-pressed]')[2].click()",
    "hoverflow": (
        "var d=document.documentElement;var bad=[];"
        "document.querySelectorAll('body *').forEach(function(e){"
        "var r=e.getBoundingClientRect();"
        "if((r.width>innerWidth+1)&&getComputedStyle(e).overflowX!=='auto'&&"
        "getComputedStyle(e).overflowX!=='scroll')"
        "bad.push(e.tagName+'.'+String(e.className).slice(0,60)+'@w'+Math.round(r.width))});"
        "d.setAttribute('data-probe',JSON.stringify({docW:d.scrollWidth,vw:innerWidth,"
        "bad:bad.slice(0,5)}))"
    ),
    "hscan": (
        "var d=document.documentElement;var bad=[];"
        "document.querySelectorAll('body *').forEach(function(e){"
        "var r=e.getBoundingClientRect();var cs=getComputedStyle(e);"
        "if(r.right>innerWidth+1||r.left<-1){"
        "if(cs.overflowX==='auto'||cs.overflowX==='scroll')return;"
        "bad.push(e.tagName+'.'+String(e.className).slice(0,55)+'|L'+Math.round(r.left)"
        "+' R'+Math.round(r.right)+' W'+Math.round(r.width))}});"
        "d.setAttribute('data-probe',JSON.stringify({docW:d.scrollWidth,vw:innerWidth,"
        "sl:d.scrollLeft,bodyW:document.body.scrollWidth,bad:bad.slice(0,8)}))"
    ),
    "kbdrow": (
        "var r=document.querySelector('tr[role=\\'button\\']');r.focus();"
        "r.dispatchEvent(new KeyboardEvent('keydown',{key:'Enter',bubbles:true}));"
        "setTimeout(function(){var d=document.querySelector('[role=dialog]');"
        "document.documentElement.setAttribute('data-probe',JSON.stringify({"
        "rowFocused:document.activeElement!==document.body,"
        "dialogOpen:!!d,dialogName:d?d.getAttribute('aria-labelledby'):null,"
        "namedBy:d&&d.getAttribute('aria-labelledby')?"
        "(document.getElementById(d.getAttribute('aria-labelledby'))||{}).textContent:null,"
        "focusInside:!!(d&&d.contains(document.activeElement))}))},400)"
    ),
    "dlg": (
        "var r=document.querySelector('tr[role=\\'button\\']');r.focus();r.dispatchEvent(new KeyboardEvent('keydown',{key:'Enter',bubbles:true}));setTimeout(function(){var shell = document.querySelector('div.fixed.inset-0.z-50');\nvar links = shell ? shell.querySelectorAll('a,button') : [];\nvar reachable = 0;\nlinks.forEach(function (el) {\n  el.focus();\n  if (document.activeElement === el) reachable++;\n});\nvar dlg = document.querySelector('[role=dialog][aria-labelledby]');\ndocument.documentElement.setAttribute('data-probe', JSON.stringify({\n  drawerInert: shell ? shell.hasAttribute('inert') : null,\n  drawerFocusables: links.length,\n  stillReachable: reachable,\n  recordDialogNamed: dlg ? (document.getElementById(dlg.getAttribute('aria-labelledby')) || {}).textContent : 'none'\n}));\n},600)"
    ),
    "errs": (
        "setTimeout(function(){document.documentElement.setAttribute('data-probe',"
        "JSON.stringify((window.__errs||[]).slice(0,4)))},900)"
    ),
    "measure": (
        "var d=document.documentElement;var over=[];"
        "document.querySelectorAll('body *').forEach(function(e){"
        "var r=e.getBoundingClientRect();"
        "if(r.bottom>innerHeight+1&&r.height>0)over.push(e.tagName+'.'+e.className+'@'+"
        "Math.round(r.top)+'+'+Math.round(r.height))});"
        "d.setAttribute('data-probe',JSON.stringify({sh:d.scrollHeight,ih:innerHeight,"
        "bh:document.body.scrollHeight,over:over.slice(0,6)}))"
    ),
}


class H(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *a, **k): super().__init__(*a, directory=DIST, **k)
    def log_message(self, *a): pass
    def _json(self, obj):
        b = json.dumps(obj).encode()
        self.send_response(200); self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(b))); self.end_headers(); self.wfile.write(b)
    def do_POST(self):
        u = urllib.parse.urlparse(self.path)
        n = int(self.headers.get("Content-Length", 0))
        body = json.loads(self.rfile.read(n) or b"{}")
        if u.path == "/api/admin/texts/preview":
            rendered = body.get("body", "")
            for k, v in (body.get("sample") or {}).items():
                rendered = rendered.replace("{" + k + "}", str(v))
            return self._json({"rendered": rendered})
        return self._json({})

    def do_GET(self):
        u = urllib.parse.urlparse(self.path)
        q = urllib.parse.parse_qs(u.query)
        n = int(q.get("days", ["14"])[0])
        if u.path == "/api/admin/dashboard/stats": return self._json(stats(n))
        if u.path == "/api/admin/dashboard/analytics": return self._json(analytics(n))
        if u.path == "/api/admin/dashboard/retention": return self._json(RETENTION)
        if u.path == "/api/admin/system/health": return self._json(HEALTH)
        if u.path == "/api/admin/broadcast/":
            langs = [c for c in q.get("languages", [""])[0].split(",") if c]
            pool = langs or list(LANG_POP)
            n = sum(LANG_POP.get(c, 0) for c in pool)
            # Same two refinements the endpoint applies, so the reach bar shrinks the way it will.
            if q.get("only_active", ["false"])[0] == "true":
                n = round(n * 0.42)
            if q.get("only_referrers", ["false"])[0] == "true":
                n = round(n * 0.28)
            return self._json({"recipients": n})
        if u.path == "/api/admin/broadcast/drafts":
            return self._json(BROADCAST_DRAFTS)
        if u.path == "/api/admin/broadcast/history":
            return self._json(BROADCAST_HISTORY)
        if u.path == "/api/admin/users/":
            return self._json(users_page(int(q.get("page", ["1"])[0]),
                                         int(q.get("page_size", ["25"])[0]),
                                         q.get("status", [""])[0], q.get("search", [""])[0],
                                         q.get("location", [""])[0]))
        if u.path == "/api/admin/dashboard/usage":
            return self._json(usage(int(q.get("days", ["14"])[0])))
        if u.path == "/api/admin/users/locations":
            return self._json(CLAIM_LOCATIONS)
        if u.path == "/api/admin/users/export.csv":
            body = "telegram_id,status,language,referrals,panel_username,location,joined\n"
            self.send_response(200)
            self.send_header("Content-Type", "text/csv; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers(); self.wfile.write(body.encode()); return
        if u.path.startswith("/api/admin/users/") and u.path.endswith("/detail"):
            uid = int(u.path.split("/")[-2])
            return self._json(user_detail(uid))
        if u.path.startswith("/api/admin/users/"):
            uid = int(u.path.rsplit("/", 1)[-1])
            return self._json({"telegram_id": uid, "status": "active_config", "language": "fa",
                               "referral_count": 27, "panel_username": "gozar_7f3a",
                               "reminder_enabled": True, "referred_by": 5_000_000_000,
                               "created_at": "2026-03-14T09:20:00Z", "configs": 11})
        if u.path == "/api/admin/site/settings/": return self._json(SITE_SETTINGS)
        if u.path == "/api/admin/site/setup/status": return self._json({"completed": True})
        if u.path == "/api/admin/site/stats/analytics": return self._json(SITE_ANALYTICS)
        if u.path == "/api/admin/site/stats/": return self._json(SITE_STATS)
        if u.path == "/api/admin/site/push/history": return self._json(SITE_PUSH_HISTORY)
        if u.path == "/api/admin/site/push/audience":
            return self._json({"recipients": 1490,
                               "by_locale": [{"locale": "fa", "count": 1120},
                                             {"locale": "en", "count": 370}]})
        if u.path == "/api/admin/site/devices/": return self._json(SITE_DEVICES)
        if u.path.startswith("/api/admin/site/devices/") and u.path.endswith("/peers"):
            return self._json(SITE_DEVICES["items"][:3])
        if u.path.startswith("/api/admin/site/devices/"):
            d = dict(SITE_DEVICES["items"][0])
            d.update({"rewards": ["pwa", "push"],
                      "recent_claims": [{"location": "Germany", "is_change": False,
                                         "created_at": "2026-08-03T10:00:00Z"},
                                        {"location": "Finland", "is_change": True,
                                         "created_at": "2026-08-02T10:00:00Z"}]})
            return self._json(d)
        if u.path == "/api/admin/site/content/": return self._json(SITE_COPY)
        if u.path == "/api/admin/site/faq/": return self._json(SITE_FAQ)
        if u.path == "/api/admin/site/pages/": return self._json(SITE_PAGES)
        if u.path == "/api/admin/site/inbox/": return self._json(SITE_MESSAGES)
        if u.path == "/api/admin/site/inbox/unread": return self._json({"unread": 3})
        if u.path == "/api/admin/texts/": return self._json(TEXTS)
        if u.path == "/api/admin/buttons/": return self._json(BUTTONS)
        if u.path == "/api/admin/settings/": return self._json(BOT_SETTINGS)
        if u.path == "/api/admin/system/history":
            return self._json(history(int(q.get("minutes", ["60"])[0])))
        if u.path == "/api/admin/site/setup/locations": return self._json(SQUAD_LOCATIONS)
        if u.path == "/api/admin/setup/status": return self._json({"completed": True})
        if u.path == "/api/admin/setup/squads":
            return self._json([{"uuid": "sq-1", "name": "Trial Squad"},
                               {"uuid": "sq-2", "name": "Paid Squad"}])
        if u.path.startswith("/api/"): return self._json({})
        if u.path.startswith("/admin/"):
            p = os.path.join(DIST, u.path[len("/admin/"):])
            if not os.path.isfile(p): return self._shell(q)
            self.path = u.path[len("/admin"):]
        return super().do_GET()

    def _shell(self, q):
        """index.html with a bootstrap script — the session, theme and locale must exist BEFORE the
        app module runs, and headless chrome has no other way to seed localStorage on this origin."""
        html = open(os.path.join(DIST, "index.html"), encoding="utf-8").read()
        boot = json.dumps({
            "theme": q.get("theme", ["dark"])[0],
            "locale": q.get("locale", ["fa"])[0],
            "fill": FILLS.get(q.get("fill", [""])[0], ""),
        })
        script = ("<script>(function(){var b=%s;"
                  "localStorage.setItem('gozarx_admin_access','x.y.z');"
                  "localStorage.setItem('gozarx_admin_refresh','x.y.z');"
                  "localStorage.setItem('gozarx_admin_user','admin');"
                  "localStorage.setItem('theme',b.theme);"
                  "localStorage.setItem('locale',b.locale);"
                  "window.__errs=[];window.addEventListener('error',function(e){"
                  "window.__errs.push(String(e.message)+' @'+(e.filename||'')+':'+e.lineno)});"
                  "var _ce=console.error;console.error=function(){"
                  "window.__errs.push([].slice.call(arguments).map(String).join(' ').slice(0,400));"
                  "_ce.apply(console,arguments)};"
                  "window.addEventListener('load',function(){"
                  "if(b.fill)setTimeout(function(){try{eval(b.fill)}catch(e){console.error(e)}},900)"
                  "})})()</script>") % boot
        body = html.replace("<head>", "<head>" + script, 1).encode()
        self.send_response(200); self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body))); self.end_headers()
        self.wfile.write(body)

socketserver.TCPServer.allow_reuse_address = True
with socketserver.TCPServer(("127.0.0.1", 4174), H) as s:
    s.serve_forever()
