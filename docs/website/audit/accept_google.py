"""Search acceptance, driven against the built site + mockapi.py: the site as GOOGLE gets it. Phase 31
found why Search Console left 8 of 32 pages "Discovered – currently not indexed" by crawling and
rendering the site as Googlebot — every page Google rendered led with the claim widget's error card
(its renderer honours robots.txt for a page's own requests, and /api/ is closed), the sitemap a
fresh server handed out listed no landing, ~20 `/?loc=` copies of the homepage were open to the
crawl, and the five guides were one text. This keeps all four from coming back. Needs the same
setup as audit.py:

    cd frontend/site && npm run build
    python3 docs/website/audit/mockapi.py &
    BACKEND_ORIGIN=http://127.0.0.1:8000 npx next start -p 3100 &
    python3 docs/website/audit/accept_google.py OUTDIR

Not covered here, because it needs the server restarted: with the backend DOWN when the site
boots, /sitemap.xml must answer a 5xx, never the fixed pages alone (checked by hand in phase 31).
Writes OUTDIR/accept-google.json; exits non-zero if any check fails.
"""

from __future__ import annotations

import json
import pathlib
import re
import sys
import urllib.error
import urllib.request
from html.parser import HTMLParser
from urllib.parse import urlparse

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from audit import BASE, find_chrome  # noqa: E402

GOOGLEBOT = "Mozilla/5.0 (compatible; Googlebot/2.1; +http://www.google.com/bot.html)"
GOOGLEBOT_PHONE = (
    "Mozilla/5.0 (Linux; Android 6.0.1; Nexus 5X Build/MMB29P) AppleWebKit/537.36 (KHTML, like "
    "Gecko) Chrome/141.0.0.0 Mobile Safari/537.36 (compatible; Googlebot/2.1; "
    "+http://www.google.com/bot.html)"
)
# The share of one guide's 5-word runs that another guide may repeat. One text with the name
# swapped measured 0.92–0.99; written per platform, 0.38–0.54 (the widget step and two shared
# troubleshooting answers are the same on purpose).
GUIDE_OVERLAP_MAX = 0.6


def fetch(path: str, ua: str = GOOGLEBOT):
    """(status, headers, body) as a crawler asks: no cookie, no Accept-Language."""
    req = urllib.request.Request(BASE + path, headers={"User-Agent": ua})  # noqa: S310 — local site
    try:
        with urllib.request.urlopen(req) as r:  # noqa: S310
            return (
                r.status,
                {k.lower(): v for k, v in r.headers.items()},
                r.read().decode(),
            )
    except urllib.error.HTTPError as e:
        return e.code, {k.lower(): v for k, v in e.headers.items()}, e.read().decode()


class MainText(HTMLParser):
    """The words inside <main>, skipping scripts and styles."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.depth = 0  # inside <main>
        self.skip = 0
        self.words: list[str] = []

    def handle_starttag(self, tag, attrs):  # noqa: ANN001 — HTMLParser's signature
        if tag == "main":
            self.depth += 1
        elif tag in ("script", "style", "svg", "template"):
            self.skip += 1

    def handle_endtag(self, tag):  # noqa: ANN001
        if tag == "main":
            self.depth -= 1
        elif tag in ("script", "style", "svg", "template"):
            self.skip -= 1

    def handle_data(self, data):  # noqa: ANN001
        if self.depth > 0 and self.skip == 0:
            self.words += re.findall(r"[\w‌]+", data)


def shingles(words: list[str], n: int = 5) -> set[str]:
    return {" ".join(words[i : i + n]) for i in range(max(0, len(words) - n + 1))}


def main() -> int:
    out = pathlib.Path(sys.argv[1] if len(sys.argv) > 1 else ".")
    out.mkdir(parents=True, exist_ok=True)
    results: list[dict] = []

    def record(name: str, ok: bool, **detail) -> None:
        results.append({"check": name, "ok": bool(ok), **detail})
        print(
            f"{'PASS' if ok else 'FAIL'}  {name}  {json.dumps(detail, ensure_ascii=False)[:400]}"
        )

    # 1) robots.txt — /api/ and the personal routes closed, and the homepage's ?loc= copies --------
    _, _, robots = fetch("/robots.txt")
    disallowed = re.findall(r"(?im)^disallow:\s*(\S+)", robots)
    site = re.search(r"(?im)^sitemap:\s*(\S+)/sitemap\.xml", robots)
    origin = site.group(1) if site else None
    record(
        "robots.txt closes /api/, /status, /offline and every /?loc= copy of the homepage",
        {"/api/", "/status", "/offline", "/*?loc="} <= set(disallowed),
        disallowed=disallowed,
    )

    # 2) the sitemap — rendered per request, every published landing in it, lastmod only real -----
    status, headers, sm = fetch("/sitemap.xml")
    entries = re.findall(r"<url>(.*?)</url>", sm, re.DOTALL)
    locs = [re.search(r"<loc>([^<]+)</loc>", e).group(1) for e in entries]
    paths = [urlparse(u).path or "/" for u in locs]
    _, _, pages_json = fetch("/api/public/pages")
    published = sorted({row["slug"] for row in json.loads(pages_json)})
    missing = [s for s in published if f"/l/{s}" not in paths]
    fixed_with_lastmod = [
        urlparse(re.search(r"<loc>([^<]+)</loc>", e).group(1)).path
        for e in entries
        if "<lastmod>" in e and "/l/" not in e
    ]
    record(
        "sitemap.xml is rendered per request and lists every published landing",
        status == 200
        and "x-nextjs-cache" not in headers
        and not missing
        and len(published) > 0,
        status=status,
        cache=headers.get("x-nextjs-cache"),
        urls=len(locs),
        missing=missing,
    )
    record(
        "sitemap.xml carries lastmod only where it is real (a landing's updated_at)",
        not fixed_with_lastmod,
        fixed_with_lastmod=fixed_with_lastmod,
    )

    # 3) every sitemap URL as Googlebot fetches it: 200, indexable, self canonical, Persian --------
    bad = []
    texts: dict[str, list[str]] = {}
    for path in paths:
        st, hd, body = fetch(path)
        robots_meta = re.search(r'<meta name="robots" content="([^"]*)"', body)
        canonical = re.search(r'<link rel="canonical" href="([^"]*)"', body)
        lang = re.search(r'<html[^>]*\slang="([a-z]+)"', body)
        want = (origin or "") + ("" if path == "/" else path)
        problems = []
        if st != 200:
            problems.append(f"HTTP {st}")
        if robots_meta and "noindex" in robots_meta.group(1):
            problems.append("noindex")
        if "noindex" in (hd.get("x-robots-tag") or ""):
            problems.append("x-robots-tag noindex")
        if not canonical or canonical.group(1).rstrip("/") != want.rstrip("/"):
            problems.append(f"canonical {canonical and canonical.group(1)}")
        if not lang or lang.group(1) != "fa":
            problems.append(f"lang {lang and lang.group(1)}")
        if problems:
            bad.append({path: problems})
        if path.startswith("/guides/"):
            parser = MainText()
            parser.feed(body)
            texts[path] = parser.words
    record(
        "every sitemap URL answers Googlebot 200, indexable, self-canonical, in Persian",
        not bad and len(paths) > 0,
        urls=len(paths),
        bad=bad,
    )

    # 4) no guide is another guide with the name swapped -----------------------------------------
    sh = {p: shingles(w) for p, w in texts.items()}
    worst = {}
    for p, mine in sh.items():
        share, other = max(
            (
                (len(mine & theirs) / len(mine), q)
                for q, theirs in sh.items()
                if q != p and mine
            ),
            default=(0.0, None),
        )
        worst[p] = {"shared": round(share, 2), "with": other}
    record(
        f"no guide repeats more than {GUIDE_OVERLAP_MAX:.0%} of another guide's text",
        len(worst) == 5
        and all(v["shared"] <= GUIDE_OVERLAP_MAX for v in worst.values()),
        guides=worst,
    )

    # 5) the widget as Google renders it: the requests robots.txt disallows are refused ----------
    landings = json.loads(pages_json)
    by_loc = next((r for r in landings if r.get("location_remark")), None)
    article = next((r for r in landings if not r.get("location_remark")), None)
    targets = ["/"] + [f"/l/{r['slug']}" for r in (by_loc, article) if r]

    from playwright.sync_api import sync_playwright

    with sync_playwright() as p:
        browser = p.chromium.launch(executable_path=find_chrome())

        def render(path: str, block: bool, cookies: dict | None = None):
            ctx = browser.new_context(
                user_agent=GOOGLEBOT_PHONE,
                locale="fa-IR",
                viewport={"width": 412, "height": 732},
            )
            if cookies:
                ctx.add_cookies(
                    [{"name": k, "value": v, "url": BASE} for k, v in cookies.items()]
                )
            page = ctx.new_page()
            refused: list[str] = []
            if block:

                def guard(route, request):  # noqa: ANN001 — Playwright's signature
                    rel = request.url.split(urlparse(BASE).netloc, 1)[-1]
                    if rel.startswith(("/api/", "/status", "/offline")):
                        refused.append(rel.split("?")[0])
                        return route.abort()
                    return route.continue_()

                page.route("**/*", guard)
            page.goto(BASE + path, wait_until="networkidle")
            page.wait_for_timeout(1500)
            state = page.evaluate(
                "() => { const w = document.querySelector('[data-view]');"
                " const on = w && w.querySelector('[role=radio][aria-checked=true]');"
                " return { view: w && w.dataset.view, cards: w ? w.querySelectorAll('[role=radio]').length : 0,"
                " checked: on && on.innerText.trim() }; }"
            )
            name = ("google" if block else "visitor") + path.replace("/", "_")
            page.screenshot(path=str(out / f"{name}.png"))
            ctx.close()
            return state, sorted(set(refused))

        for path in targets:
            state, refused = render(path, block=True)
            row = by_loc if by_loc and path == f"/l/{by_loc['slug']}" else None
            preselected = (
                not row
                or (state.get("checked") or "").find(row["location_remark"]) >= 0
            )
            record(
                f"{path}: Google's render shows the picker, not the error card",
                state.get("view") == "s1"
                and state.get("cards", 0) > 0
                and preselected
                and refused,
                state=state,
                refused=refused,
                preselect=row and row["location_remark"],
            )

        # a server that ANSWERS with an error is still the honest S8 — the fallback is for silence
        state, _ = render("/", block=False, cookies={"mock_state": "error"})
        record(
            "a /status that answers with an error still shows S8",
            state.get("view") == "s8",
            state=state,
        )
        browser.close()

    (out / "accept-google.json").write_text(
        json.dumps(results, ensure_ascii=False, indent=1)
    )
    failed = [r for r in results if not r["ok"]]
    print(f"\n{len(results) - len(failed)}/{len(results)} passed")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
