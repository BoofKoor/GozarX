"""A dependency-free stand-in for the PUBLIC site API (`/api/public/*`) — the site's twin of
`docs/panel/mockapi.py`. It lets the real, built Next.js site render every state of the claim widget
and every page without Postgres, Redis or a Remnawave panel, so the UI can be reviewed by RENDERING
it rather than by reading it.

    cd frontend/site && npm run build
    python3 docs/website/audit/mockapi.py                      # → http://127.0.0.1:8000
    PORT=3100 BACKEND_ORIGIN=http://127.0.0.1:8000 npx next start -p 3100

Response shapes are copied from the pydantic models in `backend/gozar/web/routes/public/*.py`; the
landing pages and FAQ are the REAL seeded rows (`backend/gozar/seed_landings.py`, `seed_faq.py`), and
location names are plain Persian remarks — the seed documents that production remarks look like
«آلمان», not «🇩🇪 Germany».

The browser picks a scenario with cookies (Next's `/api` rewrite forwards them here):

| cookie        | values                                                            | default  |
|---------------|-------------------------------------------------------------------|----------|
| `mock_state`  | new · active · fresh · cooldown · cooldown0 · exhausted ·         | new      |
|               | blocked · error                                                   |          |
| `mock_claim`  | ok · not_ready · no_locations · location_unavailable ·            | ok       |
|               | rate_limited · rate_limited_once · turnstile_failed ·             |          |
|               | panel_error · blocked (blocked under an open picker)              |          |
| `mock_locs`   | fa (22 Persian remarks) · en (English remarks) · few (3) · none    | fa       |
| `mock_delay`  | milliseconds to stall GET /status (skeleton / loading capture)     | 0        |
| `mock_claim_ms` | milliseconds POST /claim takes (the "taking longer" label at 3s) | 900      |
| `mock_turnstile` | 1 = /config reports Turnstile on (Cloudflare's always-pass test key) | off   |
| `mock_hist`   | 0 · 3                                                              | 3 if used|
| `mock_refs`   | cap = the invite cap is reached (10 / 10)                          | 3 / 10   |

State is per `mock_sid` cookie (set on first contact), so a claim moves THAT browser from `new` to
a delivered config exactly like the real flow does. Changing the `mock_state` cookie mid-session
re-applies it — that is how a test flips `exhausted` to `active` under a page that is polling.

Timing is real: `cooldown` lifts 7h12m after the session starts and `cooldown0` 20s after, at which
point `/status` answers claimable — so a countdown can be watched reaching zero and recovering.
Both endpoints carry `expires_at` / `cooldown_until` / `server_time` like the backend. `blocked` is
a device the operator blocked right after a claim: like the backend it still reports the cooldown
it is inside, which the widget must NOT count down — nothing is waiting at the end of it.
"""

from __future__ import annotations

import importlib.util
import json
import os
import pathlib
import threading
import time
import uuid
from datetime import UTC, datetime
from http.cookies import SimpleCookie
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, unquote, urlparse

# The two figures the homepage renders SERVER-side. Next reads /config and /stats from its own
# process, so no browser cookie can pick them per scenario — set these to prove a chip follows the
# backend rather than a constant (e.g. MOCK_TRIAL_HOURS=12, MOCK_DELIVERED=900 hides the count chip).
TRIAL_HOURS = int(os.environ.get("MOCK_TRIAL_HOURS", "24"))
DELIVERED = int(os.environ.get("MOCK_DELIVERED", "48213"))

ROOT = pathlib.Path(__file__).resolve().parents[3]
PORT = int(os.environ.get("MOCK_PORT", "8000"))


def _load(module: str, attr: str):
    spec = importlib.util.spec_from_file_location(module, ROOT / "backend" / "gozar" / f"{module}.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)  # type: ignore[union-attr]
    return getattr(mod, attr)


LANDINGS = _load("seed_landings", "DEFAULT_SITE_LANDINGS")
FAQ = _load("seed_faq", "DEFAULT_SITE_FAQ")

LOCS = {
    "fa": [
        "آلمان", "هلند", "فنلاند", "ترکیه", "آمریکا", "انگلیس", "فرانسه", "سوئد", "امارات", "کانادا",
        "ژاپن", "آذربایجان", "کره جنوبی", "ارمنستان", "لهستان", "ایتالیا", "اسپانیا", "سوئیس",
        "اتریش", "رومانی", "سنگاپور", "اوکراین",
    ],
    "en": [
        "Germany", "Netherlands", "Finland", "Turkey", "United States", "United Kingdom", "France",
        "Sweden", "United Arab Emirates", "Canada", "Japan", "Azerbaijan",
    ],
    "few": ["آلمان", "هلند", "فنلاند"],
    "none": [],
}

MB = 1024 * 1024
LIMIT = 1024 * MB
LINK = (
    "vless://a1b2c3d4-e5f6-7890-ab12-cd34ef567890@de1.gozarx.net:443?type=ws&security=tls"
    "&sni=gozarx.net&path=%2Fws#GozarX-%D8%A2%D9%84%D9%85%D8%A7%D9%86"
)

SESSIONS: dict[str, dict] = {}
LOCK = threading.Lock()


def _iso(t: float) -> str:
    return datetime.fromtimestamp(t, UTC).isoformat()


def _human(seconds: float) -> str:
    """The backend's rounded human duration ("7h 12m", "0m")."""
    total = int(seconds)
    if total <= 0:
        return "0m"
    h, m = total // 3600, (total % 3600) // 60
    return f"{h}h {m}m" if h and m else (f"{h}h" if h else f"{m}m")


COOLDOWN_FOR = {"cooldown": 7 * 3600 + 12 * 60, "cooldown0": 20}
EXPIRES_IN = 14 * 3600 + 50 * 60


def _status(sess: dict) -> dict:
    now = time.time()
    # a cooldown session whose window has passed is simply a fresh, claimable device
    if sess["state"] in COOLDOWN_FOR and now >= sess["until"]:
        sess["state"] = "new"
    state = sess["state"]
    loc = sess.get("location") or "آلمان"
    base = {
        "status": "available",
        "active": False,
        "has_config": False,
        "live": True,
        "data_exhausted": False,
        "daily_limit": "1 GB",
        "daily_limit_bytes": LIMIT,
        "usage": "—",
        "usage_bytes": 0,
        "remaining": "—",
        "cooldown": "",
        "expires_at": None,
        "cooldown_until": None,
        "server_time": _iso(now),
        "can_claim": True,
        "configs": 0,
        "referral_count": 3,
        "referral_cap": 10,
        "streak_count": 3,
        "streak_days": 7,
        "streak_active": False,
        "trial_hours": TRIAL_HOURS,
        "location": None,
        "link": None,
        "history": [],
        "handle": "GZ-7KQ4-M2XP",
        "ref_code": "GZ-7KQ4-M2XP",
    }
    hist = [
        {"location": "آلمان", "at": "2026-09-29T08:10:00Z"},
        {"location": "هلند", "at": "2026-09-28T07:55:00Z"},
        {"location": "فنلاند", "at": "2026-09-27T21:40:00Z"},
    ]
    if state in ("active", "fresh", "exhausted"):
        used = {"active": 380 * MB, "fresh": 0, "exhausted": LIMIT}[state]
        base.update(
            status="active_config",
            active=True,
            has_config=True,
            data_exhausted=state == "exhausted",
            usage="380 MB" if state == "active" else ("0 B" if state == "fresh" else "1 GB"),
            usage_bytes=used,
            remaining=_human(sess["expires"] - now),
            expires_at=_iso(sess["expires"]),
            can_claim=False,
            cooldown=_human(sess["expires"] - now),
            cooldown_until=_iso(sess["expires"]),
            configs=4,
            location=loc,
            link=LINK,
            history=hist,
        )
    elif state == "blocked":
        base.update(
            status="blocked",
            can_claim=False,
            cooldown=_human(sess["expires"] - now),
            cooldown_until=_iso(sess["expires"]),
            configs=4,
            history=hist,
        )
    elif state in ("cooldown", "cooldown0"):
        base.update(
            can_claim=False,
            cooldown=_human(sess["until"] - now),
            cooldown_until=_iso(sess["until"]),
            configs=4,
            history=hist,
        )
    if sess.get("bonus"):
        base.update(referral_count=4, daily_limit="1.5 GB", daily_limit_bytes=LIMIT + 500 * MB)
    if sess.get("hist") == "0":
        base["history"] = []
    if sess.get("refs") == "cap":
        base["referral_count"] = base["referral_cap"]
    return base


class Handler(BaseHTTPRequestHandler):
    server_version = "gozar-site-mock/1"

    def log_message(self, fmt, *args):  # quiet: one line per request is noise for a render loop
        if os.environ.get("MOCK_VERBOSE"):
            super().log_message(fmt, *args)

    # ---- plumbing -------------------------------------------------------------------------------
    def _cookies(self) -> dict[str, str]:
        jar = SimpleCookie()
        jar.load(self.headers.get("cookie", ""))
        return {k: unquote(v.value) for k, v in jar.items()}

    def _session(self) -> tuple[dict, str | None]:
        c = self._cookies()
        sid = c.get("mock_sid")
        new_cookie = None
        wanted = c.get("mock_state", "new")
        with LOCK:
            if not sid or sid not in SESSIONS:
                sid = sid or uuid.uuid4().hex
                SESSIONS[sid] = {"location": None}
                new_cookie = sid
            sess = SESSIONS[sid]
            if sess.get("cookie_state") != wanted:  # first contact, or the test flipped the cookie
                now = time.time()
                # exhausted → active under a live page is the revive a friend's first claim causes:
                # one more invite and the referral reward on the allowance, like the backend
                revive = sess.get("cookie_state") == "exhausted" and wanted == "active"
                sess.update(cookie_state=wanted, state=wanted, expires=now + EXPIRES_IN,
                            until=now + COOLDOWN_FOR.get(wanted, 0), attempts=0, bonus=revive)
        sess["claim"] = c.get("mock_claim", "ok")
        sess["locs"] = c.get("mock_locs", "fa")
        sess["delay"] = int(c.get("mock_delay", "0") or 0)
        sess["claim_ms"] = int(c.get("mock_claim_ms", "900") or 900)
        sess["turnstile"] = c.get("mock_turnstile") == "1"
        sess["hist"] = c.get("mock_hist")
        sess["refs"] = c.get("mock_refs")
        return sess, new_cookie

    def _send(self, code: int, payload, set_sid: str | None = None) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode()
        self.send_response(code)
        self.send_header("content-type", "application/json; charset=utf-8")
        self.send_header("content-length", str(len(body)))
        if set_sid:
            self.send_header("set-cookie", f"mock_sid={set_sid}; Path=/; SameSite=Lax")
        self.end_headers()
        self.wfile.write(body)

    def _body(self) -> dict:
        n = int(self.headers.get("content-length") or 0)
        if not n:
            return {}
        try:
            return json.loads(self.rfile.read(n))
        except ValueError:
            return {}

    # ---- GET ------------------------------------------------------------------------------------
    def do_GET(self):  # noqa: N802 — http.server's naming
        url = urlparse(self.path)
        q = {k: v[0] for k, v in parse_qs(url.query).items()}
        path = url.path.removeprefix("/api/public")
        locale = q.get("locale")

        if path == "/site-copy":
            return self._send(200, {"hero_title": None, "hero_sub": None, "meta_title": None,
                                    "meta_description": None, "overrides": {}})
        if path == "/faq":
            rows = [
                {"cat": r["category"], "q": r["question"], "a": r["answer"]}
                for r in FAQ
                if r["locale"] == (locale or "fa")
            ]
            return self._send(200, rows)
        if path == "/pages":
            rows = [
                {k: r[k] for k in ("slug", "locale", "title", "meta_description", "location_remark")}
                | {"updated_at": "2026-09-01T00:00:00Z"}
                for r in LANDINGS
                if not locale or r["locale"] == locale or (locale == "en")
            ]
            return self._send(200, rows)
        if path.startswith("/pages/"):
            slug = path.split("/", 2)[2]
            for r in LANDINGS:
                if r["slug"] == slug:
                    return self._send(200, dict(r) | {"updated_at": "2026-09-01T00:00:00Z"})
            return self._send(404, {"detail": "not_found"})

        sess, sid = self._session()
        if path == "/status":
            if sess["delay"]:
                time.sleep(sess["delay"] / 1000)
            if sess["state"] == "error":
                return self._send(502, {"detail": "panel_error"}, sid)
            return self._send(200, _status(sess), sid)
        if path == "/config":
            return self._send(200, {
                # Cloudflare's documented always-pass test key: the widget really loads and answers
                "turnstile_site_key": "1x00000000000000000000AA" if sess["turnstile"] else "",
                "vapid_public_key": "BMockVapidPublicKeyForRenderingOnly0000000000000000000000000000000000000000000",
                "turnstile_enabled": sess["turnstile"],
                "popular_location": "آلمان" if sess["locs"] != "en" else "Germany",
                "reward_referral_mb": 500,
                "reward_pwa_mb": 200,
                "reward_push_mb": 150,
                "reward_streak_mb": 300,
                "streak_days": 7,
                "trial_hours": TRIAL_HOURS,
            }, sid)
        if path == "/locations":
            return self._send(200, {"locations": LOCS.get(sess["locs"], LOCS["fa"])}, sid)
        if path == "/stats":
            return self._send(200, {"configs_delivered": DELIVERED, "uptime_pct": 99.7}, sid)
        return self._send(404, {"detail": "not_found"}, sid)

    # ---- POST -----------------------------------------------------------------------------------
    def do_POST(self):  # noqa: N802
        path = urlparse(self.path).path.removeprefix("/api/public")
        body = self._body()
        sess, sid = self._session()
        if path == "/claim":
            time.sleep(sess["claim_ms"] / 1000)  # long enough to screenshot the provisioning state
            outcome = sess["claim"]
            sess["attempts"] = sess.get("attempts", 0) + 1
            if outcome == "rate_limited" or (outcome == "rate_limited_once" and sess["attempts"] == 1):
                return self._send(429, {"detail": "rate_limited"}, sid)
            if outcome == "turnstile_failed":
                return self._send(403, {"detail": "turnstile_failed"}, sid)
            if outcome == "blocked" or sess["state"] == "blocked":
                sess["state"] = "blocked"  # the next /status reports it, as the backend's would
                return self._send(200, {"ok": False, "reason": "blocked", "changed": False,
                                        "server_time": _iso(time.time())}, sid)
            if outcome in ("not_ready", "no_locations", "panel_error"):
                return self._send(200, {"ok": False, "reason": outcome, "changed": False}, sid)
            if outcome == "location_unavailable":
                return self._send(200, {"ok": False, "reason": "location_unavailable",
                                        "changed": False, "locations": LOCS["few"]}, sid)
            if sess["state"] in COOLDOWN_FOR:
                return self._send(200, {"ok": False, "reason": "cooldown", "changed": False,
                                        "retry_after": _human(sess["until"] - time.time()),
                                        "cooldown_until": _iso(sess["until"]),
                                        "server_time": _iso(time.time())}, sid)
            changed = sess["state"] in ("active", "fresh", "exhausted")
            if not changed:
                sess["expires"] = time.time() + 24 * 3600 - 60
            sess["state"] = "fresh" if not changed else "active"
            sess["location"] = body.get("location") or "آلمان"
            return self._send(200, {"ok": True, "location": sess["location"], "link": LINK,
                                    "expires": _human(sess["expires"] - time.time()),
                                    "expires_at": _iso(sess["expires"]),
                                    "server_time": _iso(time.time()),
                                    "size": "1 GB", "changed": changed}, sid)
        if path == "/rewards/claim":
            if sess["state"] == "blocked":
                return self._send(200, {"ok": False, "reason": "blocked"}, sid)
            return self._send(200, {"ok": True, "reward_type": body.get("reward_type"),
                                    "amount_mb": 150, "streak_active": False,
                                    "new_daily": "1.1 GB"}, sid)
        if path == "/transfer/create":
            return self._send(200, {"ok": True, "code": "K7M2XQ9P", "expires_in": 600}, sid)
        if path == "/transfer/redeem":
            ok = str(body.get("code", "")).upper().replace("-", "") == "K7M2XQ9P"
            return self._send(200, {"ok": ok, "reason": None if ok else "invalid",
                                    "has_config": ok, "referral_count": 3}, sid)
        if path == "/device/reset":
            sess["state"] = "new"
            return self._send(200, {"ok": True}, sid)
        if path == "/contact":
            return self._send(200, {"ok": bool(body.get("body"))}, sid)
        if path in ("/push/subscribe", "/push/unsubscribe"):
            return self._send(200, {"ok": True}, sid)
        return self._send(404, {"detail": "not_found"}, sid)


def main() -> None:
    srv = ThreadingHTTPServer(("127.0.0.1", PORT), Handler)
    print(f"site mock API on http://127.0.0.1:{PORT}/api/public/  (Ctrl-C to stop)")
    srv.serve_forever()


if __name__ == "__main__":
    main()
