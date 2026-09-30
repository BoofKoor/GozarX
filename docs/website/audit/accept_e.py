"""Phase E acceptance, driven against the built site + mockapi.py — content, information architecture
and trust: the status page named for what it holds, /about and /contact as two pages, legal pages a
reader can navigate, a 404 and an offline page with somewhere to go, one FAQ source, copy that only
states what the backend does, the config link as a QR code, and the transfer and settings flows
saying what they are about to do. Needs the same setup as audit.py:

    cd frontend/site && npm run build
    python3 docs/website/audit/mockapi.py &
    BACKEND_ORIGIN=http://127.0.0.1:8000 npx next start -p 3100 &
    python3 docs/website/audit/accept_e.py OUTDIR

The QR check decodes the rendered code with `zxingcpp` (`pip install zxing-cpp`) when it is
installed, and otherwise checks its structure only. Writes OUTDIR/accept-e.json and a few
screenshots; exits non-zero if any check fails.
"""

from __future__ import annotations

import json
import pathlib
import sys
import urllib.request

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from audit import BASE, find_chrome, make_context, settle  # noqa: E402

MOCK = "http://127.0.0.1:8000/api/public"
PAGES = ("/", "/status", "/faq", "/contact", "/about", "/locations")


def mock_json(path: str):
    with urllib.request.urlopen(MOCK + path) as r:  # noqa: S310 — the local mock
        return json.load(r)


def main() -> int:
    out = pathlib.Path(sys.argv[1] if len(sys.argv) > 1 else ".")
    out.mkdir(parents=True, exist_ok=True)
    from playwright.sync_api import sync_playwright

    results: list[dict] = []

    def record(name: str, ok: bool, **detail) -> None:
        results.append({"check": name, "ok": bool(ok), **detail})
        print(f"{'PASS' if ok else 'FAIL'}  {name}  {json.dumps(detail, ensure_ascii=False)[:400]}")

    with sync_playwright() as p:
        browser = p.chromium.launch(executable_path=find_chrome())

        def open_page(path: str, vp="m390", locale="fa", **kw):
            ctx = make_context(browser, vp, locale, "light", **kw)
            page = ctx.new_page()
            resp = page.goto(BASE + path, wait_until="networkidle")
            settle(page, 400)
            return ctx, page, resp

        # 1) D1 — the status page is «کانفیگ من», everywhere it is named ---------------------------
        stale: dict[str, list[str]] = {}
        for locale, old in (("fa", "حساب کاربری"), ("en", "Account")):
            for path in PAGES:
                ctx, page, _ = open_page(path, "d1280", locale)
                text = page.evaluate("document.body.innerText")
                labels = page.evaluate(
                    "[...document.querySelectorAll('a[href=\"/status\"]')].map(a => (a.getAttribute('aria-label') || a.innerText).trim())"
                )
                hits = [line for line in text.split("\n") if old in line and (locale == "fa" or line.strip() == old)]
                if hits or any(lbl == old for lbl in labels):
                    stale[f"{locale} {path}"] = hits[:3] + labels
                ctx.close()
        ctx, page, _ = open_page("/status", "m390", "fa", cookies={"mock_state": "active"})
        title = page.title()
        ctx.close()
        record("D1: no «حساب کاربری» / \"Account\" label on 6 pages × 2 languages; /status has its own title",
               not stale and title.startswith("کانفیگ من"), stale=stale, status_title=title)

        # 2) /about and /contact are two pages -----------------------------------------------------
        ctx, page, _ = open_page("/about")
        about = page.evaluate(
            "({h1: document.querySelector('main h1')?.innerText, cards: document.querySelectorAll('.about-card').length,"
            " privacy: !!document.querySelector('.about-card a[href=\"/privacy\"]'), text: document.querySelector('main').innerText})"
        )
        page.screenshot(path=str(out / "e-about.png"), full_page=True)
        ctx.close()
        ctx, page, _ = open_page("/contact")
        contact = page.evaluate(
            "({h1: document.querySelector('main h1')?.innerText, text: document.querySelector('main').innerText,"
            " form: !!document.querySelector('main form, main textarea'), about: !!document.querySelector('main a[href=\"/about\"]')})"
        )
        ctx.close()
        body = "هدف ما ساده است"
        record("C-33: /about and /contact have their own headings and text",
               about["h1"] == "دربارهٔ ما" and about["cards"] == 3 and about["privacy"]
               and contact["h1"] == "تماس با ما" and contact["form"] and contact["about"]
               and body in about["text"] and body not in contact["text"],
               about_h1=about["h1"], cards=about["cards"], contact_h1=contact["h1"])

        # 3) legal pages: numbered contents that resolve, a real date, the switch ------------------
        for path in ("/terms", "/privacy"):
            ctx, page, _ = open_page(path, "d1280")
            legal = page.evaluate("""() => {
              const toc = [...document.querySelectorAll('.toc a')];
              const heads = [...document.querySelectorAll('.legal-body h2')];
              return {
                toc: toc.map(a => a.innerText.trim()),
                resolve: toc.every(a => !!document.getElementById(a.getAttribute('href').slice(1))),
                nums: heads.map(h => h.querySelector('.n')?.innerText),
                sticky: getComputedStyle(document.querySelector('.toc')).position,
                updated: document.querySelector('.updated')?.innerText,
                current: document.querySelector('.legal-switch a[aria-current=page]')?.getAttribute('href'),
              };
            }""")
            if path == "/terms":
                page.screenshot(path=str(out / "e-terms.png"), full_page=True)
            ctx.close()
            numbered = legal["nums"] == [f"{n}." for n in "۱۲۳۴۵۶۷۸۹"[: len(legal["nums"])]]
            record(f"C-34: {path} — numbered contents that resolve, sticky from 900px, a dated revision",
                   len(legal["toc"]) == len(legal["nums"]) > 0 and legal["resolve"] and numbered
                   and legal["sticky"] == "sticky" and legal["current"] == path
                   and legal["updated"] == "آخرین به‌روزرسانی: مهر ۱۴۰۵",
                   **legal)

        # 4) 404: a search that lands on the FAQ, and somewhere to go ------------------------------
        ctx, page, resp = open_page("/no-such-page")
        nf = page.evaluate(
            "({h1: document.querySelector('main h1')?.innerText, links: document.querySelectorAll('.nf-links a').length,"
            " action: document.querySelector('form.nf-search')?.getAttribute('action')})"
        )
        page.fill("form.nf-search input[name=q]", "وصل")
        page.click("form.nf-search button[type=submit]")
        page.wait_for_url("**/faq?q=*", timeout=8000)
        settle(page, 400)
        landed = page.evaluate(
            "({q: document.querySelector('.idx-search input')?.value, shown: document.querySelectorAll('.acc').length})"
        )
        ctx.close()
        record("C-35: 404 answers 404, names the page, and its search lands on the FAQ pre-filled",
               resp.status == 404 and nf["h1"] == "صفحه پیدا نشد" and nf["links"] == 6
               and nf["action"] == "/faq" and landed["q"] == "وصل" and landed["shown"] > 0,
               status=resp.status, **nf, landed=landed)

        # 5) one FAQ source: the home teaser is the panel's first five; nothing found → ask --------
        faq = mock_json("/faq?locale=fa")
        ctx, page, _ = open_page("/")
        teaser = page.evaluate("[...document.querySelectorAll('#faq .acc-head')].map(b => b.innerText.trim())")
        ctx.close()
        ctx, page, _ = open_page("/faq?q=zzzz")
        empty = page.evaluate(
            "({text: document.querySelector('.faq-empty')?.innerText, ask: document.querySelector('.faq-empty a')?.getAttribute('href')})"
        )
        ctx.close()
        want = [row["q"] for row in faq[:5]]
        record("C-36: the home FAQ is the panel's first five questions; an empty search offers «بپرس»",
               teaser[:5] == want and empty["ask"] == "/contact" and len(faq) >= 12,
               teaser=teaser[:5], panel=want, faq_rows=len(faq), empty=empty)

        # 6) copy states only what the backend does ------------------------------------------------
        live = mock_json("/locations")["locations"]
        ctx, page, _ = open_page("/", "d1280")
        page.evaluate("document.getElementById('locations')?.scrollIntoView()")
        page.wait_for_timeout(600)
        home = page.evaluate(
            "({sub: document.querySelector('#locations .sec-sub')?.innerText, how: document.body.innerText})"
        )
        ctx.close()
        ctx, page, _ = open_page("/locations", "d1280")
        intro = page.evaluate("document.querySelector('.loc-intro p')?.innerText")
        ctx.close()
        record("C-53: the locations sentences name the squad's live list; no «آنلاین و آماده», no «ده‌ها کشور»",
               home["sub"] and live[0] in home["sub"] and "اوکراین" not in home["sub"]
               and intro and live[0] in intro and "ده‌ها کشور" not in intro
               and "آنلاین و آماده" not in home["how"] and "کلاینت‌های محبوب" not in home["how"],
               home_sub=home["sub"], intro=intro, live_first=live[:3])

        # 7) the config link as a QR code that decodes to the link --------------------------------
        ctx, page, _ = open_page("/", cookies={"mock_state": "active"})
        link = page.evaluate("document.querySelector('.copyfield code')?.innerText")
        page.click(".cfg-actions .icon-btn")
        page.wait_for_selector(".qr-box svg[role=img]", timeout=8000)
        qr = page.evaluate(
            "(() => { const s = document.querySelector('.qr-box svg'); const vb = s.viewBox.baseVal;"
            " return {size: vb.width, path: s.querySelector('path').getAttribute('d').length,"
            " expanded: document.querySelector('.cfg-actions .icon-btn').getAttribute('aria-expanded')}; })()"
        )
        shot = out / "e-qr.png"
        page.locator(".qr-box").screenshot(path=str(shot))
        page.screenshot(path=str(out / "e-qr-widget.png"))
        ctx.close()
        decoded = None
        try:
            import zxingcpp  # type: ignore[import-not-found]
            from PIL import Image

            found = zxingcpp.read_barcodes(Image.open(shot))
            decoded = found[0].text if found else ""
        except ImportError:
            pass
        record("C-09: «کد QR» opens a code of the config link" + (" (decoded)" if decoded is not None else " (structure only)"),
               qr["size"] >= 29 and qr["path"] > 100 and qr["expanded"] == "true"
               and (decoded is None or decoded == link),
               link=link, decoded=decoded, **qr)

        # 8) offline: the last config comes back, from the widget AND from /offline ----------------
        # One offline navigation per context: Playwright's offline emulation reliably covers the
        # service worker's first fetch after set_offline, not a restarted worker's later ones — so
        # a second navigation could reach the live server and pass or fail for the wrong reason.
        def offline_page(path: str, wait: str):
            ctx = make_context(browser, "m390", "fa", "light", cookies={"mock_state": "active"})
            page = ctx.new_page()
            page.goto(BASE + "/status", wait_until="networkidle")
            page.evaluate("navigator.serviceWorker.ready.then(() => true)")
            page.reload(wait_until="networkidle")  # now controlled: the shell is cached
            settle(page, 600)
            saved = page.evaluate("JSON.parse(localStorage.getItem('gz_last_config') || 'null')")
            ctx.set_offline(True)
            page.goto(BASE + path, wait_until="load")
            page.wait_for_selector(wait, timeout=10000)
            return ctx, page, saved

        ctx, page, saved = offline_page("/status", "[data-saved-config]")
        widget = page.evaluate("document.querySelector('[data-saved-config] code')?.innerText")
        page.screenshot(path=str(out / "e-offline-widget.png"), full_page=True)
        ctx.close()
        ctx, page, _ = offline_page("/somewhere-never-visited", ".offline-cfg")
        offline = page.evaluate(
            "({h1: document.querySelector('main h1')?.innerText, link: document.querySelector('.offline-cfg code')?.innerText,"
            " note: document.querySelector('.offline-cfg .oc-note')?.innerText, label: document.querySelector('.offline-cfg b')?.innerText})"
        )
        page.screenshot(path=str(out / "e-offline-page.png"), full_page=True)
        ctx.close()
        record("C-35/C-67: offline, the saved config is on /status (S8) and on /offline",
               saved and saved.get("link") and widget == saved["link"] and offline["link"] == saved["link"]
               and offline["h1"] == "آفلاین هستی" and offline["note"],
               saved=saved and {k: saved.get(k) for k in ("label", "expires_at")}, widget=widget, offline=offline)

        # 9) transfer: a browser with data is asked first; a fresh one sees "restore" first -------
        ctx, page, _ = open_page("/status", cookies={"mock_state": "active"})
        page.fill(".code-input input", "K7M2-XQ9P")
        page.click(".code-input .btn")
        page.wait_for_selector(".restore-warn[role=alert]", timeout=4000)
        warn = page.evaluate("document.querySelector('.restore-warn p')?.innerText")
        page.click(".restore-warn .btn.ghost")
        gone = page.evaluate("!document.querySelector('.restore-warn')")
        ctx.close()
        ctx, page, _ = open_page("/status", cookies={"mock_state": "new", "mock_refs": "0", "mock_hist": "0"})
        first = page.evaluate("document.querySelector('.transfer-card h2')?.innerText")
        ctx.close()
        record("C-17: restoring over this browser's data asks first; a fresh browser sees «restore» first",
               bool(warn) and gone and first == "قبلاً از GozarX استفاده کرده‌ای؟", warn=warn, fresh_first=first)

        # 10) settings + reset say what is going on ----------------------------------------------
        ctx = make_context(browser, "m390", "fa", "light", cookies={"mock_state": "active"})
        ctx.add_init_script("Object.defineProperty(Notification, 'permission', {get: () => 'denied'})")
        page = ctx.new_page()
        page.goto(BASE + "/status", wait_until="networkidle")
        settle(page, 500)
        why = page.evaluate("document.querySelector('.srow .skd-why')?.innerText")
        page.click(".srow .skd-why .link-btn")
        # `.modal`: the phone menu is a role=dialog too, mounted and inert while closed
        page.wait_for_selector(".modal[role=dialog]", timeout=4000)
        dialog = page.evaluate("document.querySelector('.modal[role=dialog] h2')?.innerText")
        page.keyboard.press("Escape")
        page.click(".danger-row .btn.danger")
        page.click(".modal[role=dialog] .btn.danger.block")
        page.wait_for_selector(".toast-wrap .toast", timeout=6000)
        # the toast's own wrapper: the rewards card mounts a `.toast-wrap` of its own
        toast = page.evaluate("document.querySelector('.toast-wrap .toast')?.innerText")
        region = page.evaluate("document.querySelector('.toast-wrap .toast')?.parentElement.getAttribute('role')")
        ctx.close()
        record("C-20/C-21: a blocked switch says why (and how), a reset says it happened",
               bool(why) and bool(dialog) and toast and region == "status", why=why, dialog=dialog,
               toast=toast)

        browser.close()

    (out / "accept-e.json").write_text(json.dumps(results, ensure_ascii=False, indent=1))
    failed = [r["check"] for r in results if not r["ok"]]
    print(f"\n{len(results) - len(failed)}/{len(results)} passed" + (f" — FAILED: {failed}" if failed else ""))
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
