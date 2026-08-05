#!/usr/bin/env python3
"""Deterministic mock of GozarX's public backend, for the Phase 0 render harness.

Read-only audit tooling. Serves the `/api/public/*` surface the site actually calls, so every
screen state can be summoned on demand instead of waiting for a real device to drift into it.

Response shapes are transcribed from the SOURCE, not from memory:
  - frontend/site/lib/api.ts            (StatusResponse, ClaimResponse, PublicConfig, PublicStats)
  - backend/gozar/web/routes/public/*.py (the Pydantic models behind each endpoint)

The current state is global and switched with `POST /__state {"name": "..."}` so the capture script
can drive it between navigations. States map onto the widget's own S1..S8 comments in
frontend/site/components/ClaimWidget.tsx.

Usage:  python3 mockapi.py [port]      (default 8000, matching BACKEND_ORIGIN's default)
"""

from __future__ import annotations

import json
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

# --- state ------------------------------------------------------------------------------------

# Each entry tunes /status, /locations and POST /claim together, because the widget derives its
# screen from all three (ClaimWidget.tsx:185-197).
STATES = {
    # S1 idle picker — a first-time visitor, locations on offer, nothing claimed yet.
    "first": {},
    # S3 fresh claim — POST /claim succeeds with changed=false (the celebration view).
    "claim_ok": {"claim": "ok"},
    # S4 returning — the device already holds today's config.
    "delivered": {"has_config": True, "status": "active_config", "active": True,
                  "usage_bytes": 268435456, "usage": "256 MB", "remaining": "768 MB",
                  "configs": 7, "can_claim": False, "cooldown": "۵ ساعت و ۲۰ دقیقه"},
    # S6 revive — the daily allowance is spent.
    "exhausted": {"has_config": True, "status": "active_config", "active": True,
                  "data_exhausted": True, "usage_bytes": 1073741824, "usage": "1 GB",
                  "remaining": "0 B", "configs": 9, "can_claim": False},
    # S5 cooldown — claimed today, next one is hours away, config no longer live.
    "cooldown": {"can_claim": False, "cooldown": "۵ ساعت و ۲۰ دقیقه", "configs": 4,
                 "claim": "cooldown"},
    # S7 no locations — the squad serves nothing right now.
    "no_locations": {"locations": []},
    # S8 panel error — /status itself fails, which is what drives `offline` in useSite.ts.
    "panel_error": {"status_http": 502},
    # Security guard: POST /claim returns 429 {detail} (lib/api.ts:111 turns it into ok=false).
    "rate_limited": {"claim": "rate_limited"},
    # The squad stopped serving the picked location between render and claim.
    "location_unavailable": {"claim": "location_unavailable"},
    # Turnstile required — the claim CTA is gated on a Cloudflare script.
    "turnstile": {"turnstile": True},
    # Everything slow: exercises the loading skeleton and the perceptual-threshold questions.
    "slow": {"delay": 3.0},
}

_state_name = "first"
_lock = threading.Lock()


def cfg() -> dict:
    with _lock:
        return STATES.get(_state_name, {})


# --- fixtures ---------------------------------------------------------------------------------

LOCATIONS = [
    "\U0001F1E9\U0001F1EA Germany", "\U0001F1F3\U0001F1F1 Netherlands", "\U0001F1EB\U0001F1F7 France",
    "\U0001F1EC\U0001F1E7 United Kingdom", "\U0001F1F8\U0001F1EA Sweden", "\U0001F1F9\U0001F1F7 Turkey",
    "\U0001F1E6\U0001F1EA UAE", "\U0001F1FA\U0001F1F8 United States", "\U0001F1EB\U0001F1EE Finland",
    "\U0001F1F5\U0001F1F1 Poland", "\U0001F1E6\U0001F1F9 Austria", "\U0001F1E8\U0001F1E6 Canada",
]

# A realistic VLESS link: long, Latin, and dropped into RTL Persian chrome — exactly the bidi case
# Phase 2 has to look at.
LINK = (
    "vless://8f3c1d2e-9a4b-4c7d-b1e6-2f5a8c9d0e13@de-01.gozarx-edge.net:443"
    "?type=ws&security=tls&sni=cdn.gozarx-edge.net&host=cdn.gozarx-edge.net"
    "&path=%2Fws%3Fed%3D2048&fp=chrome&alpn=h2%2Chttp%2F1.1#GozarX-DE-01"
)


def status_body() -> dict:
    c = cfg()
    base = {
        "status": "available",
        "active": False,
        "has_config": False,
        "live": True,
        "data_exhausted": False,
        "daily_limit": "1 GB",
        "daily_limit_bytes": 1073741824,
        "usage": "0 B",
        "usage_bytes": 0,
        "remaining": "1 GB",
        "cooldown": "",
        "can_claim": True,
        "configs": 0,
        "referral_count": 3,
        "referral_cap": 10,
        "streak_count": 2,
        "streak_days": 5,
        "streak_active": False,
        "trial_hours": 24,
        "location": None,
        "link": None,
        "history": [],
        "handle": "GZ-7QK2M4",
        "ref_code": "GZ-7QK2M4",
    }
    base.update({k: v for k, v in c.items()
                 if k in base})
    if base["has_config"]:
        base["location"] = LOCATIONS[0]
        base["link"] = LINK
        base["history"] = [
            {"location": LOCATIONS[0], "at": iso_ago(3 * 3600)},
            {"location": LOCATIONS[1], "at": iso_ago(28 * 3600)},
            {"location": LOCATIONS[4], "at": iso_ago(52 * 3600)},
        ]
    return base


def iso_ago(seconds: float) -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(time.time() - seconds))


def config_body() -> dict:
    on = bool(cfg().get("turnstile"))
    return {
        # A real-looking key so the widget takes the turnstile branch; the script itself is blocked
        # by the capture harness, which is the point of that state.
        "turnstile_site_key": "0x4AAAAAAABkMYinukE8nzYS" if on else "",
        "vapid_public_key": "BEl62iUYgUivxIkv69yViEuiBIa1HI0wQVeZ2VYCJ1kQ8bF5Y2xX7QpZ3nT4kL9m",
        "turnstile_enabled": on,
        "popular_location": LOCATIONS[0],
        "reward_referral_mb": 500,
        "reward_pwa_mb": 200,
        "reward_push_mb": 200,
        "reward_streak_mb": 300,
        "streak_days": 5,
    }


def claim_body() -> tuple[int, dict]:
    mode = cfg().get("claim", "ok")
    if mode == "rate_limited":
        return 429, {"detail": "rate_limited"}
    if mode == "cooldown":
        return 200, {"ok": False, "reason": "cooldown", "changed": False,
                     "retry_after": "۵ ساعت و ۲۰ دقیقه"}
    if mode == "location_unavailable":
        return 200, {"ok": False, "reason": "location_unavailable", "changed": False,
                     "locations": LOCATIONS[1:5]}
    if mode == "panel_error":
        return 200, {"ok": False, "reason": "panel_error", "changed": False}
    return 200, {
        "ok": True, "reason": None, "location": LOCATIONS[0], "link": LINK,
        "expires": iso_ago(-24 * 3600), "size": "1 GB", "changed": False, "retry_after": None,
    }


FAQ = {
    "fa": [
        {"cat": "شروع", "q": "چطور کانفیگ رایگان بگیرم؟",
         "a": "یک لوکیشن انتخاب کن و دکمهٔ دریافت را بزن."},
        {"cat": "شروع", "q": "آیا به ثبت‌نام نیاز دارد؟",
         "a": "خیر. نه ایمیل، نه شماره."},
        {"cat": "حجم", "q": "حجم روزانه چقدر است؟",
         "a": "۱ گیگابایت، و با دعوت دوستان بیشتر می‌شود."},
    ],
    "en": [
        {"cat": "Getting started", "q": "How do I get a free config?",
         "a": "Pick a location and press the get button."},
        {"cat": "Getting started", "q": "Do I need to sign up?", "a": "No. No email, no phone."},
        {"cat": "Volume", "q": "How much daily volume?",
         "a": "1 GB, and it grows when you invite friends."},
    ],
}

LANDINGS = [
    {"slug": "free-v2ray-config-germany", "locale": "fa",
     "title": "کانفیگ رایگان آلمان — گذرایکس",
     "meta_description": "کانفیگ رایگان آلمان.",
     "location_remark": LOCATIONS[0], "updated_at": iso_ago(86400)},
    {"slug": "what-is-vless", "locale": "fa",
     "title": "VLESS چیست؟ — گذرایکس",
     "meta_description": "معرفی پروتکل VLESS.",
     "location_remark": None, "updated_at": iso_ago(172800)},
    {"slug": "best-free-vpn-iran", "locale": "fa",
     "title": "بهترین فیلترشکن رایگان — گذرایکس",
     "meta_description": "راهنمای انتخاب.",
     "location_remark": None, "updated_at": iso_ago(259200)},
]

LANDING_BODY = (
    "<h2>چرا این صفحه؟</h2>"
    "<p>این یک متن نمونه برای "
    "ممیزی است. لینک نمونه: "
    "<code>vless://8f3c1d2e-9a4b-4c7d-b1e6-2f5a8c9d0e13@de-01.example.net:443</code> "
    "و عدد 1024 در دل جملهٔ فارسی.</p>"
    "<ul><li>مورد اول</li><li>مورد دوم</li></ul>"
)


# --- server -----------------------------------------------------------------------------------

class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, *args):  # keep the capture run's output readable
        pass

    # -- helpers
    def _send(self, code: int, payload, set_cookie: bool = False):
        raw = json.dumps(payload).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(raw)))
        self.send_header("Cache-Control", "no-store")
        if set_cookie:
            # Mirrors the real signed device cookie (identity.py:28 DEVICE_COOKIE).
            self.send_header("Set-Cookie",
                             "gz_device=mock-device-uuid.mocksig; Path=/; HttpOnly; SameSite=Lax")
        self.end_headers()
        self.wfile.write(raw)

    def _delay(self):
        d = cfg().get("delay")
        if d:
            time.sleep(float(d))

    # -- routes
    def do_GET(self):
        u = urlparse(self.path)
        q = parse_qs(u.query)
        loc = (q.get("locale") or ["fa"])[0]
        p = u.path
        self._delay()

        if p == "/api/public/status":
            http = cfg().get("status_http")
            if http:
                return self._send(int(http), {"detail": "panel_error"})
            return self._send(200, status_body(), set_cookie=True)
        if p == "/api/public/config":
            return self._send(200, config_body())
        if p == "/api/public/locations":
            if cfg().get("status_http"):
                return self._send(502, {"detail": "panel_error"})
            return self._send(200, {"locations": cfg().get("locations", LOCATIONS)})
        if p == "/api/public/stats":
            return self._send(200, {"configs_delivered": 1284309, "uptime_pct": 99.4})
        if p == "/api/public/faq":
            return self._send(200, FAQ.get(loc, FAQ["fa"]))
        if p == "/api/public/site-copy":
            return self._send(200, {"hero_title": None, "hero_sub": None, "meta_title": None,
                                    "meta_description": None, "overrides": {}})
        if p == "/api/public/pages":
            return self._send(200, LANDINGS)
        if p.startswith("/api/public/pages/"):
            slug = p.rsplit("/", 1)[-1]
            row = next((r for r in LANDINGS if r["slug"] == slug), None)
            if not row:
                return self._send(404, {"detail": "not_found"})
            return self._send(200, {**row, "heading": row["title"].split("—")[0].strip(),
                                    "body": LANDING_BODY})
        if p == "/health":
            return self._send(200, {"ok": True, "state": _state_name})
        return self._send(404, {"detail": "not_found"})

    def do_POST(self):
        global _state_name
        u = urlparse(self.path)
        p = u.path
        length = int(self.headers.get("Content-Length") or 0)
        raw = self.rfile.read(length) if length else b"{}"
        try:
            body = json.loads(raw or b"{}")
        except Exception:
            body = {}

        # Harness control channel — not part of the product's API.
        if p == "/__state":
            with _lock:
                _state_name = body.get("name", "first")
            return self._send(200, {"ok": True, "state": _state_name})

        self._delay()
        if p == "/api/public/claim":
            code, payload = claim_body()
            return self._send(code, payload)
        if p == "/api/public/rewards/claim":
            return self._send(200, {"ok": True, "reward_type": body.get("reward_type"),
                                    "amount_mb": 200, "streak_count": 3, "streak_active": False,
                                    "new_daily": "1.2 GB"})
        if p == "/api/public/transfer/create":
            return self._send(200, {"ok": True, "code": "GZ-4M2K-9XQ1", "expires_in": 600})
        if p == "/api/public/transfer/redeem":
            return self._send(200, {"ok": True, "has_config": True, "referral_count": 3})
        if p == "/api/public/device/reset":
            return self._send(200, {"ok": True})
        if p == "/api/public/contact":
            return self._send(200, {"ok": True, "reason": None})
        if p in ("/api/public/push/subscribe", "/api/public/push/unsubscribe"):
            return self._send(200, {"ok": True})
        return self._send(404, {"detail": "not_found"})


if __name__ == "__main__":
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8000
    ThreadingHTTPServer(("127.0.0.1", port), Handler).serve_forever()
