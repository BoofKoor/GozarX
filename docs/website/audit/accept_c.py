"""Phase C acceptance, driven against the built site + mockapi.py — conversion on a phone and the
paths INTO the claim widget: the button on the first screen, a landing's widget above its article, a
location chosen elsewhere arriving chosen, and every entry point (sticky bar, header, phone menu,
footer band, reward rows, app cards, guides, the articles index) going where it says. Needs the same
setup as audit.py:

    cd frontend/site && npm run build
    python3 docs/website/audit/mockapi.py &
    BACKEND_ORIGIN=http://127.0.0.1:8000 npx next start -p 3100 &
    python3 docs/website/audit/accept_c.py OUTDIR

Writes OUTDIR/accept-c.json and a screenshot for the checks that are about where things SIT; exits
non-zero if any check fails. Checks name states (`data-view`, `aria-checked`, hrefs), not copy,
except where the copy is the point (an unfilled `{token}`, a promise the site cannot keep).
"""

from __future__ import annotations

import json
import pathlib
import re
import sys
import urllib.request
from urllib.parse import unquote

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from audit import BASE, find_chrome, make_context, settle  # noqa: E402

MOCK = "http://127.0.0.1:8000/api/public"
S1_CTA = "[data-view='s1'] button.cta:not([disabled])"
CHECKED = "document.querySelector('.loc-card[aria-checked=true] .nm')?.textContent ?? null"
TOKEN = re.compile(r"\{[a-z_]+\}")
FA_DIGITS = str.maketrans("0123456789", "۰۱۲۳۴۵۶۷۸۹")


def rect(page, selector: str):
    return page.evaluate(
        "s => { const e = document.querySelector(s); if (!e) return null;"
        " const r = e.getBoundingClientRect(); return {top: Math.round(r.top),"
        " bottom: Math.round(r.bottom), vh: innerHeight}; }",
        selector,
    )


def mock(path: str):
    with urllib.request.urlopen(MOCK + path, timeout=5) as r:
        return json.load(r)


def main() -> int:
    out = pathlib.Path(sys.argv[1] if len(sys.argv) > 1 else ".")
    out.mkdir(parents=True, exist_ok=True)
    from playwright.sync_api import sync_playwright

    results: list[dict] = []

    def record(name: str, ok: bool, **detail) -> None:
        results.append({"check": name, "ok": bool(ok), **detail})
        print(f"{'PASS' if ok else 'FAIL'}  {name}  {json.dumps(detail, ensure_ascii=False)}")

    config = mock("/config")
    articles = {r["slug"] for r in mock("/pages") if not r["location_remark"]}

    with sync_playwright() as p:
        browser = p.chromium.launch(executable_path=find_chrome())

        def open_page(path: str, vp="m390", locale="fa", theme="light", **kw):
            ctx = make_context(browser, vp, locale, theme, **kw)
            page = ctx.new_page()
            page.goto(BASE + path, wait_until="networkidle")
            settle(page, 400)
            return ctx, page

        # 1) the claim button on the first screen (plan: home-fa-fold-m360 / -m390) ----------------
        for vp in ("m360", "m390"):
            for locale in ("fa", "en"):
                ctx, page = open_page("/", vp, locale)
                page.wait_for_selector(S1_CTA, timeout=8000)
                r = rect(page, S1_CTA)
                if locale == "fa":
                    page.screenshot(path=str(out / f"c-fold-home-{vp}.png"))
                record(f"home {locale} {vp}: claim CTA fully on the first screen",
                       r["bottom"] <= r["vh"], cta_bottom=r["bottom"], viewport=r["vh"])
                ctx.close()

        # 2) a landing's widget above its article (plan: landing-germany-fa-fold-m390) -------------
        ctx, page = open_page("/l/vpn-germany")
        page.wait_for_selector(S1_CTA, timeout=8000)
        w = rect(page, ".landing-widget .widget")
        c = rect(page, S1_CTA)
        body = rect(page, ".landing-body")
        title = page.evaluate("document.querySelector('.landing-widget .w-title')?.textContent")
        picked = page.evaluate(CHECKED)
        page.screenshot(path=str(out / "c-fold-landing-germany-m390.png"))
        record("landing: widget + CTA above the fold, before the article, named and preselected",
               w["top"] < w["vh"] and c["bottom"] <= c["vh"] and w["bottom"] <= body["top"]
               and picked == "آلمان" and "آلمان" in (title or ""),
               widget_top=w["top"], cta_bottom=c["bottom"], title=title, checked=picked)
        ctx.close()

        # 3) /locations → «هلند» arrives chosen (plan) ---------------------------------------------
        ctx, page = open_page("/locations")
        page.click(".loccell:has(.ln:text-is('هلند'))")
        page.wait_for_url(re.compile(r"/\?loc="), timeout=8000)
        page.wait_for_selector(S1_CTA, timeout=8000)
        page.wait_for_function(f"{CHECKED} === 'هلند'", timeout=5000)
        url = unquote(page.url)
        page.screenshot(path=str(out / "c-locations-nl.png"))
        record("/locations «هلند» → home with هلند selected",
               page.evaluate(CHECKED) == "هلند", url=url[len(BASE):])
        ctx.close()

        # 4) the homepage flags pick, and a NEW pick wins over an earlier manual one ---------------
        ctx, page = open_page("/")
        page.wait_for_selector(S1_CTA, timeout=8000)
        page.click(".loc-card:has(.nm:text-is('ترکیه'))")
        manual = page.evaluate(CHECKED)
        page.click(".fbig-link[aria-label='فنلاند']")
        page.wait_for_url(re.compile(r"loc="), timeout=8000)
        ok = True
        try:
            page.wait_for_function(f"{CHECKED} === 'فنلاند'", timeout=5000)
        except Exception:
            ok = False
        record("home flag strip picks its location (over an earlier manual pick)",
               ok and manual == "ترکیه", manual=manual, after_flag=page.evaluate(CHECKED))
        ctx.close()

        # 5) the sticky bar: only while the widget is away, never over another CTA ------------------
        def sticky(page):
            return page.evaluate(
                "(() => { const s = document.querySelector('.sticky-cta'); if (!s) return null;"
                " const r = s.getBoundingClientRect(); const cs = getComputedStyle(s);"
                " return {show: s.classList.contains('show'), display: cs.display,"
                " visible: cs.visibility === 'visible' && cs.display !== 'none' && r.top < innerHeight,"
                " label: s.textContent.trim()}; })()"
            )

        ctx, page = open_page("/")
        page.wait_for_selector(S1_CTA, timeout=8000)
        at_load = sticky(page)
        page.evaluate("document.querySelector('#how').scrollIntoView()")
        page.wait_for_timeout(700)
        away = sticky(page)
        page.screenshot(path=str(out / "c-sticky.png"))
        page.evaluate("document.querySelector('.ft-cta').scrollIntoView({block: 'center'})")
        page.wait_for_timeout(700)
        at_footer = sticky(page)
        page.evaluate("document.querySelector('#how').scrollIntoView()")
        page.wait_for_timeout(700)
        page.click(".sticky-cta button")
        page.wait_for_timeout(1200)
        back = rect(page, "#hero-widget")
        focused = page.evaluate("document.activeElement?.classList.contains('w-title')")
        record("sticky bar: hidden at load, shown once the widget is away, steps aside for the footer"
               " CTA, and takes you back to the widget heading",
               not at_load["visible"] and away["visible"] and not at_footer["visible"]
               and 0 <= back["top"] <= 150 and focused,
               at_load=at_load["visible"], away=away["visible"], at_footer=at_footer["visible"],
               widget_top_after_tap=back["top"], heading_focused=focused)
        ctx.close()

        for label, kw, want in (
            ("cooldown: nothing to claim, no bar", {"cookies": {"mock_state": "cooldown"}}, None),
            ("config holder: the bar says «کانفیگ من»", {"cookies": {"mock_state": "active"}},
             "کانفیگ من"),
            ("desktop: never", {"vp": "d1280"}, None),
        ):
            ctx, page = open_page("/", **kw)
            page.wait_for_selector("[data-view]:not([data-view=loading])", timeout=8000)
            page.evaluate("document.querySelector('#how').scrollIntoView()")
            page.wait_for_timeout(700)
            s = sticky(page)
            ok = s["visible"] and want in s["label"] if want else not s["visible"]
            record(f"sticky bar — {label}", ok, **s)
            ctx.close()

        # 6) header shortcut (desktop, pages without a widget) + the phone menu ---------------------
        ctx, page = open_page("/guides", vp="d1280")
        on_guides = page.evaluate(
            "(() => { const a = document.querySelector('.hd-cta');"
            " return a && getComputedStyle(a).display !== 'none' ? a.getAttribute('href') : null; })()"
        )
        page.goto(BASE + "/", wait_until="networkidle")
        on_home = page.evaluate("!!document.querySelector('.hd-cta')")
        record("header: «دریافت کانفیگ» on inner pages, not where a widget already is",
               on_guides == "/#hero-widget" and not on_home, guides=on_guides, home=on_home)
        ctx.close()

        ctx, page = open_page("/guides")
        page.click("button.burger")
        page.wait_for_timeout(500)
        menu = page.evaluate(
            "(() => { const s = document.querySelector('#site-menu');"
            " const first = s.querySelector('a, button');"
            " const links = [...s.querySelectorAll('#sheetnav .navlink')];"
            " return {first: first?.className, firstHref: first?.getAttribute('href'),"
            " active: s.querySelector('#sheetnav .navlink.active')?.textContent.trim(),"
            " icons: links.every(a => a.querySelector('svg')), last: links.at(-1)?.getAttribute('href')}; })()"
        )
        page.screenshot(path=str(out / "c-menu.png"))
        record("phone menu: the claim action first, icons, active page marked, Home last",
               "sheet-cta" in (menu["first"] or "") and menu["firstHref"] == "/#hero-widget"
               and menu["active"] == "راهنما" and menu["icons"] and menu["last"] == "/", **menu)
        ctx.close()

        # 7) the footer band follows the visitor (V-09) --------------------------------------------
        amount = str(config["reward_referral_mb"]).translate(FA_DIGITS)
        for label, cookies, want_href, want_text in (
            ("no config yet: claim", None, "/#hero-widget", None),
            ("holds a config: invite, with the reward", {"mock_state": "active"}, "/status#rewards",
             amount),
            ("cooldown: invite", {"mock_state": "cooldown"}, "/status#rewards", amount),
            ("invite cap reached: their config", {"mock_state": "active", "mock_refs": "cap"},
             "/status", None),
        ):
            ctx, page = open_page("/faq", cookies=cookies)
            page.wait_for_timeout(600)
            band = page.evaluate(
                "(() => { const b = document.querySelector('.ft-cta');"
                " return {href: b.querySelector('a').getAttribute('href'), text: b.textContent}; })()"
            )
            ok = band["href"] == want_href and (want_text is None or want_text in band["text"])
            record(f"footer band — {label}", ok, href=band["href"], text=band["text"].strip()[:90])
            ctx.close()

        # 8) reward rows go to where the reward is earned (C-38) -----------------------------------
        ctx, page = open_page("/")
        rows = page.evaluate("[...document.querySelectorAll('#rewards .mvrow')].map(a => a.getAttribute('href'))")
        page.goto(BASE + "/status#rewards", wait_until="networkidle")
        target = page.evaluate("!!document.getElementById('rewards')")
        record("reward rows link to /status#rewards, and the anchor exists",
               len(rows) == 4 and set(rows) == {"/status#rewards"} and target, rows=rows, anchor=target)
        ctx.close()

        # 9) app cards open that app's page (C-37) --------------------------------------------------
        for ua, happ in (("android", "/guides/android"), ("ios", "/guides/ios")):
            ctx, page = open_page("/", ua=ua)
            hrefs = page.evaluate("[...document.querySelectorAll('.appcard')].map(a => a.getAttribute('href'))")
            want = {happ, "/l/v2rayng-config", "/l/streisand-config"}
            record(f"app cards ({ua}) → Happ guide for the platform + each app's article",
                   set(hrefs) == want, hrefs=hrefs)
            ctx.close()

        # 10) guides: an install source that works from Iran, the App Store caveat, a path to the
        # widget (C-28, C-29) -------------------------------------------------------------------------
        ctx, page = open_page("/guides/android")
        g = page.evaluate(
            "(() => ({apk: document.querySelector('.dlbtn')?.href,"
            " play: document.querySelector('.dl-alt')?.href,"
            " get: document.querySelector('.guide-get')?.getAttribute('href')}))()"
        )
        record("android guide: APK first, Google Play second, step 2 links to the widget",
               (g["apk"] or "").startswith("https://github.com/Happ-proxy/")
               and (g["apk"] or "").endswith(".apk") and "play.google.com" in (g["play"] or "")
               and g["get"] == "/#hero-widget", **g)
        page.goto(BASE + "/guides/ios", wait_until="networkidle")
        note = page.evaluate("document.querySelector('.dl-note')?.textContent ?? null")
        record("iOS guide: says the App Store needs a non-Iranian Apple ID", bool(note) and "Apple ID" in note,
               note=note)
        ctx.close()

        # 11) the articles index lists every article, and is in the sitemap (V-08) -----------------
        ctx, page = open_page("/articles")
        cards = page.evaluate(
            "[...document.querySelectorAll('.art-card')].map(a => a.getAttribute('href').replace('/l/', ''))"
        )
        sitemap = page.request.get(BASE + "/sitemap.xml").text()
        record("/articles lists every article landing and is in the sitemap",
               set(cards) == articles and "/articles</loc>" in sitemap,
               cards=len(cards), articles=len(articles))
        page.goto(BASE + "/", wait_until="networkidle")
        home = page.evaluate("document.querySelectorAll('#articles .art-card').length")
        foot = page.evaluate(
            "[...document.querySelectorAll('.ft-more a')].map(a => a.getAttribute('href'))"
        )
        record("homepage features 4 article cards; the footer at most 5 + «all»",
               home == 4 and len(foot) <= 6 and foot[-1] == "/articles", home=home, footer=foot)
        ctx.close()

        # 12) no unfilled {token} reaches a page (the Phase B key collision printed one) -------------
        leaks = {}
        for locale in ("fa", "en"):
            ctx = make_context(browser, "d1280", locale, "light")
            page = ctx.new_page()
            for path in ("/", "/l/vpn-germany", "/locations", "/articles", "/guides/android", "/faq",
                         "/status"):
                page.goto(BASE + path, wait_until="networkidle")
                page.wait_for_timeout(300)
                found = TOKEN.findall(page.evaluate("document.body.innerText"))
                if found:
                    leaks[f"{locale} {path}"] = found
            ctx.close()
        record("no unfilled {token} in the rendered text of 7 pages × 2 languages", not leaks,
               leaks=leaks)

        # 13) the Hiddify article no longer promises an illustrated Hiddify walkthrough (V-08) -------
        ctx, page = open_page("/l/hiddify-config")
        text = page.evaluate("document.querySelector('.landing-body').innerText")
        record("Hiddify article: no «با تصویر» promise; says the guides are for Happ",
               "با تصویر" not in text and "Happ" in text)
        ctx.close()

        # 14) an anchor into the page lands BELOW the sticky header, not under it ------------------
        # (`.hero{overflow:hidden}` made the hero a scroll container, which clipped the widget's
        # scroll-margin at the hero's edge: on desktop `#hero-widget` landed at y=28, under a 69px
        # header). Fresh loads with a hash, and the desktop flag tap (a same-page navigation).
        def lands(page, target: str):
            return page.evaluate(
                "t => { const e = document.querySelector(t); const h = document.querySelector("
                "'header.hd').getBoundingClientRect().bottom; const top = e.getBoundingClientRect().top;"
                " return {top: Math.round(top), header: Math.round(h)}; }",
                target,
            )

        for vp in ("m390", "d1280"):
            for path, target in (("/?loc=%D9%87%D9%84%D9%86%D8%AF#hero-widget", "#hero-widget"),
                                 ("/status#rewards", "#rewards"), ("/status#claim", "#claim")):
                ctx, page = open_page(path, vp, cookies={"mock_state": "active"})
                page.wait_for_timeout(600)
                pos = lands(page, target)
                record(f"{vp} {path.split('?')[0].split('#')[0] or '/'}{target}: lands below the header",
                       pos["header"] <= pos["top"] <= pos["header"] + 60, **pos)
                ctx.close()
        ctx, page = open_page("/", "d1280")
        page.evaluate("document.querySelector('#locations').scrollIntoView()")
        page.wait_for_timeout(400)
        page.click(".fbig-link[aria-label='هلند']")
        page.wait_for_timeout(2000)
        pos = lands(page, "#hero-widget")
        record("d1280 flag tap: the widget lands below the header",
               pos["header"] <= pos["top"] <= pos["header"] + 60, **pos)
        ctx.close()

        # 15) the widget's reserved height is S1's own (no empty band, no shift) --------------------
        for vp in ("m360", "m390", "d1280"):
            ctx, page = open_page("/", vp)
            page.wait_for_selector(S1_CTA, timeout=8000)
            h = page.evaluate(
                "(() => { const w = document.querySelector('#hero-widget .widget');"
                " const reserved = parseFloat(getComputedStyle(w).minBlockSize);"
                " w.style.minBlockSize = '0px'; const natural = w.getBoundingClientRect().height;"
                " w.style.minBlockSize = ''; return {reserved, natural: Math.round(natural)}; })()"
            )
            record(f"S1 natural height = reservation ({vp})", abs(h["natural"] - h["reserved"]) <= 3, **h)
            ctx.close()

        browser.close()

    (out / "accept-c.json").write_text(json.dumps(results, ensure_ascii=False, indent=1))
    failed = [r["check"] for r in results if not r["ok"]]
    print(f"\n{len(results) - len(failed)}/{len(results)} passed" + (f" — FAILED: {failed}" if failed else ""))
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
