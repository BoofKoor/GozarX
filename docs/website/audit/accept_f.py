"""Phase F acceptance, driven against the built site + mockapi.py — performance and the SEO
architecture: pages that are rendered once and served from the cache instead of per visit, the
language picked per request without a second URL (decision D3), the copy dictionary out of the
JavaScript, a stylesheet a page only pays for when it uses it, a social card per landing, the
locations list in the HTML, an installable app that says what it is in both languages, and an
offline shell that keeps its styles. Needs the same setup as audit.py:

    cd frontend/site && npm run build
    python3 docs/website/audit/mockapi.py &
    BACKEND_ORIGIN=http://127.0.0.1:8000 npx next start -p 3100 &
    python3 docs/website/audit/accept_f.py OUTDIR

Weights are the first visit of a phone (390×844) with an empty cache, each response gzipped at
level 5 (nginx's `gzip_comp_level`). Writes OUTDIR/accept-f.json; exits non-zero if any check fails.
"""

from __future__ import annotations

import gzip
import json
import pathlib
import re
import struct
import sys
import urllib.error
import urllib.request

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from audit import BASE, find_chrome, make_context, settle  # noqa: E402

JS_BUDGET_KB = 160
CSS_BUDGET_KB = 10


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):  # noqa: ANN002, ANN003 — urllib's signature
        return None


def fetch(path: str, headers: dict | None = None, follow: bool = True):
    """(status, headers, body) — redirects are reported, not followed, when follow=False."""
    req = urllib.request.Request(BASE + path, headers=headers or {})  # noqa: S310 — the local site
    opener = urllib.request.build_opener() if follow else urllib.request.build_opener(_NoRedirect)
    try:
        with opener.open(req) as r:
            return r.status, {k.lower(): v for k, v in r.headers.items()}, r.read()
    except urllib.error.HTTPError as e:
        return e.code, {k.lower(): v for k, v in e.headers.items()}, e.read()


def html_lang(body: bytes) -> str | None:
    m = re.search(rb'<html[^>]*\slang="([a-z]+)"', body)
    return m.group(1).decode() if m else None


def png_size(body: bytes) -> tuple[int, int] | None:
    if body[:8] != b"\x89PNG\r\n\x1a\n":
        return None
    return struct.unpack(">II", body[16:24])


def main() -> int:
    out = pathlib.Path(sys.argv[1] if len(sys.argv) > 1 else ".")
    out.mkdir(parents=True, exist_ok=True)
    from playwright.sync_api import sync_playwright

    results: list[dict] = []

    def record(name: str, ok: bool, **detail) -> None:
        results.append({"check": name, "ok": bool(ok), **detail})
        print(f"{'PASS' if ok else 'FAIL'}  {name}  {json.dumps(detail, ensure_ascii=False)[:400]}")

    # 1) C-61 — the marketing pages are static: rendered once, then served from the cache ----------
    cached = {}
    for path in ("/", "/l/vpn-germany", "/guides/android", "/faq", "/locations"):
        fetch(path)  # the first visit after a deploy renders it
        status, headers, _ = fetch(path)
        cached[path] = {"status": status, "x-nextjs-cache": headers.get("x-nextjs-cache")}
    record(
        "pages are static/ISR — the second request is a cache HIT",
        all(v["status"] == 200 and v["x-nextjs-cache"] in ("HIT", "STALE") for v in cached.values()),
        pages=cached,
    )
    _, h, _ = fetch("/about")
    cc = h.get("cache-control", "")
    record(
        "a page is private to its visitor (one URL, two languages) and revalidated by ETag",
        "private" in cc and "no-cache" in cc and bool(h.get("etag")),
        cache_control=cc,
        etag=h.get("etag"),
    )

    # 2) D3 / C-64 — one URL per page; the language is picked per request, Persian by default ------
    langs = {
        "no cookie, no Accept-Language (a crawler)": html_lang(fetch("/about")[2]),
        "Accept-Language: en": html_lang(fetch("/about", {"Accept-Language": "en-US,en;q=0.9"})[2]),
        "cookie locale=en": html_lang(fetch("/about", {"Cookie": "locale=en"})[2]),
        "cookie locale=fa over Accept-Language: en": html_lang(
            fetch("/about", {"Cookie": "locale=fa", "Accept-Language": "en"})[2]
        ),
    }
    record(
        "language by cookie → Accept-Language → fa, on the same URL",
        list(langs.values()) == ["fa", "en", "en", "fa"],
        langs=langs,
    )
    prefixed = {p: fetch(p, follow=False)[:2] for p in ("/fa/about", "/en", "/en/l/vpn-germany")}
    record(
        "the internal /fa/… and /en/… trees are not public URLs (308 to the one address)",
        all(s == 308 for s, _ in prefixed.values())
        and prefixed["/fa/about"][1].get("location", "").endswith("/about"),
        redirects={p: (s, h.get("location")) for p, (s, h) in prefixed.items()},
    )
    body = fetch("/")[2]
    record(
        "no hreflang alternates (SEO is Persian-only)",
        b"hreflang" not in body,
    )
    nf_status, _, nf_body = fetch("/this-does-not-exist")
    record(
        "an unknown path is a 404, drawn on the server inside the site's own document",
        nf_status == 404 and b'class="hd"' in nf_body and b"nf-code" in nf_body and b"__next_error__" not in nf_body,
        status=nf_status,
    )

    # 3) C-66 — robots.txt, and a social card per landing ------------------------------------------
    robots = fetch("/robots.txt")[2].decode()
    record("robots.txt has no non-standard Host line", "host:" not in robots.lower(), robots=robots)
    og = {}
    for name in ("site", "vpn-germany"):
        s, h, b = fetch(f"/og/{name}.png")
        og[name] = {"status": s, "type": h.get("content-type"), "size": png_size(b), "bytes": len(b)}
    missing = fetch("/og/no-such-landing.png")[0]
    landing = fetch("/l/vpn-germany")[2].decode()
    og_meta = re.findall(r'<meta property="og:image" content="([^"]+)"', landing)
    tw = re.findall(r'<meta name="twitter:card" content="([^"]+)"', landing)
    record(
        "1200×630 social cards: the site's, and a location landing's own",
        all(v["status"] == 200 and v["size"] == (1200, 630) for v in og.values())
        and missing == 404
        and any(u.endswith("/og/vpn-germany.png") for u in og_meta)
        and tw == ["summary_large_image"],
        cards=og,
        unknown_slug=missing,
        og_image=og_meta,
        twitter=tw,
    )

    # 4) C-65 — the locations list is in the HTML a crawler reads -----------------------------------
    loc_html = fetch("/locations")[2].decode()
    cells = re.findall(r'class="loccell"[^>]*href="([^"]+)"|href="([^"]+)"[^>]*class="loccell"', loc_html)
    record(
        "/locations carries every location link server-side",
        len(cells) >= 10,
        cells=len(cells),
        sample=[a or b for a, b in cells[:3]],
    )

    # 5) C-68 — the installable app in each language, with its own maskable icon --------------------
    manifests = {}
    for path in ("/manifest.webmanifest", "/manifest-en.webmanifest"):
        manifests[path] = json.loads(fetch(path)[2])
    purposes = [
        sorted({i.get("purpose") for i in m["icons"]}) for m in manifests.values()
    ]
    fa_m, en_m = manifests.values()
    linked = {
        "fa": re.findall(r'<link rel="manifest" href="([^"]+)"', fetch("/")[2].decode()),
        "en": re.findall(r'<link rel="manifest" href="([^"]+)"', fetch("/", {"Cookie": "locale=en"})[2].decode()),
    }
    record(
        "two manifests, one app: shared id, their own lang/dir/description, separate maskable icons",
        fa_m["id"] == en_m["id"] == "/"
        and (fa_m["lang"], fa_m["dir"], en_m["lang"], en_m["dir"]) == ("fa", "rtl", "en", "ltr")
        and fa_m["description"] != en_m["description"]
        and all(p == ["any", "maskable"] for p in purposes)
        and linked == {"fa": ["/manifest.webmanifest"], "en": ["/manifest-en.webmanifest"]},
        linked=linked,
        purposes=purposes,
    )

    with sync_playwright() as p:
        browser = p.chromium.launch(executable_path=find_chrome())

        # 6) the first visit's weight — the page's own, and nothing prefetched behind it ------------
        def weigh(path: str) -> dict:
            ctx = make_context(browser, "m390", "fa", "light")
            ctx.clear_cookies()  # a first visit: no locale, no theme, no device
            page = ctx.new_page()
            rows: list[tuple[str, str, int, int]] = []

            def on_response(r):
                try:
                    b = r.body()
                except Exception:  # noqa: BLE001 — redirects and aborted requests have no body
                    return
                ct = (r.headers.get("content-type") or "").split(";")[0]
                kind = (
                    "js" if "javascript" in ct else "css" if "css" in ct else "rsc" if "x-component" in ct
                    else "html" if "html" in ct else "json" if "json" in ct else "other"
                )
                rows.append((kind, r.url, len(b), len(gzip.compress(b, 5))))

            page.on("response", on_response)
            page.goto(BASE + path, wait_until="networkidle")
            page.wait_for_timeout(1500)
            page.remove_listener("response", on_response)  # the bundle reads below are not part of the visit
            js_urls = [u for k, u, _, _ in rows if k == "js"]
            bundle = "".join(page.evaluate("u => fetch(u).then(r => r.text())", u) for u in js_urls)
            eager = page.evaluate(
                "() => [...document.querySelectorAll('.loc-grid .loc-card:not([hidden]) img.flag')]"
                ".map(i => i.getAttribute('loading'))"
            )
            ctx.close()
            agg: dict[str, list[float]] = {}
            for k, _, raw, gz in rows:
                a = agg.setdefault(k, [0, 0, 0])
                a[0] += raw / 1024
                a[1] += gz / 1024
                a[2] += 1
            return {
                "kb": {k: {"raw": round(v[0], 1), "gzip": round(v[1], 1), "n": v[2]} for k, v in agg.items()},
                "bundle": bundle,
                "eager": eager,
            }

        home = weigh("/")
        js = home["kb"].get("js", {}).get("gzip", 0)
        css = home["kb"].get("css", {}).get("gzip", 0)
        record(f"home first-visit JS ≤ {JS_BUDGET_KB} KB gzip", js <= JS_BUDGET_KB, kb=home["kb"])
        record(f"home first-visit CSS ≤ {CSS_BUDGET_KB} KB gzip", css <= CSS_BUDGET_KB, css=home["kb"].get("css"))
        record(
            "nothing is prefetched behind the first visit (no RSC requests)",
            "rsc" not in home["kb"],
            rsc=home["kb"].get("rsc"),
        )
        # C-56 — the bundle carries neither the other language nor the design's never-built pages
        leaks = {
            "the English hero line on a Persian first visit": "Free, fast configs" in home["bundle"],
            "the Persian hero line (it rides in the page, not the bundle)": "کانفیگ رایگان و پرسرعت" in home["bundle"],
            "a key the site never read (the dev bar)": "Platform preview:" in home["bundle"],
            "the review gallery's copy": "Simulate a successful invite" in home["bundle"],
        }
        record("the copy dictionary is out of the JavaScript", not any(leaks.values()), leaks=leaks)
        record(
            "the picker's first rows load their flags eagerly (C-63)",
            bool(home["eager"]) and all(v is None for v in home["eager"]),
            loading_attrs=home["eager"][:8],
        )
        record(
            "a first visit does not download the post-claim views",
            "copyfield" not in home["bundle"] and "cd-seg" not in home["bundle"],
        )

        # 7) the claim still delivers — the post-claim views arrive with the claim ------------------
        ctx = make_context(browser, "m390", "fa", "light")
        page = ctx.new_page()
        page.goto(BASE + "/", wait_until="networkidle")
        settle(page, 600)
        page.click(".cta-anchor button.cta")
        page.wait_for_selector('[data-view="s3"] .copyfield code', timeout=15000)
        focused = page.evaluate("document.activeElement?.tagName")
        record("a claim still lands on S3 with its link, focused on its heading", focused == "H2", focused=focused)
        ctx.close()

        # 8) the saved theme is on before the first paint of a prerendered page ----------------------
        ctx = make_context(browser, "m390", "fa", "dark")
        page = ctx.new_page()
        errors: list[str] = []
        page.on("console", lambda m: errors.append(m.text) if m.type == "error" else None)
        page.on("pageerror", lambda e: errors.append(str(e)))
        first_paint_theme = []
        page.expose_function("__probe", lambda v: first_paint_theme.append(v))
        page.add_init_script(
            "new MutationObserver((l, o) => { const a = document.getElementById('app');"
            " if (a && a.firstElementChild && a.firstElementChild.nextElementSibling) {"
            " window.__probe(a.getAttribute('data-theme')); o.disconnect(); } })"
            ".observe(document, { childList: true, subtree: true });"
        )
        page.goto(BASE + "/faq", wait_until="networkidle")
        settle(page, 400)
        record(
            "a saved dark theme is applied before #app's first child paints, with no hydration error",
            first_paint_theme[:1] == ["dark"] and not [e for e in errors if "hydrat" in e.lower()],
            at_parse=first_paint_theme[:1],
            errors=errors[:3],
        )
        ctx.close()

        # 9) C-67 — offline, the cached shell keeps its stylesheet ----------------------------------
        ctx = make_context(browser, "m390", "fa", "light", cookies={"mock_state": "active"})
        page = ctx.new_page()
        page.goto(BASE + "/status", wait_until="networkidle")
        settle(page, 800)
        page.evaluate("navigator.serviceWorker && navigator.serviceWorker.ready.then(() => true)")
        page.wait_for_timeout(2500)  # install: the shell pages and what they name
        cached_assets = page.evaluate(
            "async () => { const out = []; for (const k of await caches.keys()) {"
            " const c = await caches.open(k); for (const r of await c.keys()) out.push(new URL(r.url).pathname); }"
            " return out; }"
        )
        ctx.set_offline(True)
        page.goto(BASE + "/offline", wait_until="load")
        page.wait_for_timeout(800)
        styled = page.evaluate(
            "() => { const a = document.getElementById('app'); const cs = a && getComputedStyle(a);"
            " return { font: cs && cs.fontFamily, bg: cs && cs.backgroundColor,"
            " sheets: document.styleSheets.length, saved: !!document.querySelector('.offline-cfg code') }; }"
        )
        page.screenshot(path=str(out / "f-offline-styled.png"), full_page=False)
        ctx.close()
        record(
            "offline, /offline draws in the site's styles and hands back the saved config",
            any(a.endswith(".css") for a in cached_assets)
            and "Yekan" in (styled.get("font") or "")
            and styled.get("saved"),
            cached_css=[a for a in cached_assets if a.endswith(".css")][:3],
            styled=styled,
        )
        browser.close()

    (out / "accept-f.json").write_text(json.dumps(results, ensure_ascii=False, indent=1))
    failed = [r for r in results if not r["ok"]]
    print(f"\n{len(results) - len(failed)}/{len(results)} passed")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
