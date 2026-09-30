"""Phase D acceptance, driven against the built site + mockapi.py — the accessibility and language
plumbing: every phone control a 44px target, the menu and dialogs keeping the keyboard (and the page
behind them still), the skip link, live feedback, accordions a screen reader and Ctrl-F can reach,
a heading outline without skipped levels, the three-state theme, location names in the visitor's
language, and one volume format with no reversed «GB ۱». Needs the same setup as audit.py:

    cd frontend/site && npm run build
    python3 docs/website/audit/mockapi.py &
    BACKEND_ORIGIN=http://127.0.0.1:8000 npx next start -p 3100 &
    python3 docs/website/audit/accept_d.py OUTDIR

Writes OUTDIR/accept-d.json and a few screenshots; exits non-zero if any check fails.
"""

from __future__ import annotations

import json
import pathlib
import re
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from audit import BASE, find_chrome, make_context, settle  # noqa: E402

# Every interactive element under 44px, except a text link inside running text (WCAG 2.5.8's inline
# exception) — the same rule as audit.py's `tapUnder44`, over the whole page rather than the view.
SMALL_TARGETS = r"""() => {
  const out = [];
  for (const el of document.querySelectorAll('a[href], button, input, select, textarea, [role=button], [role=switch], [role=radio], summary')) {
    const cs = getComputedStyle(el);
    if (cs.display === 'none' || cs.visibility === 'hidden') continue;
    if (el.closest('[hidden], [inert], [aria-hidden=true], .sr-only') || el.classList.contains('skip-link')) continue;
    const r = el.getBoundingClientRect(); if (!r.width || !r.height) continue;
    if (el.tagName === 'A' && cs.display === 'inline' && el.closest('p,li')) continue;
    if (r.width < 44 || r.height < 44) {
      const txt = (el.getAttribute('aria-label') || el.innerText || '').trim().replace(/\s+/g, ' ').slice(0, 24);
      out.push(`${el.tagName.toLowerCase()}.${String(el.className).split(' ')[0]} «${txt}» ${Math.round(r.width)}×${Math.round(r.height)}`);
    }
  }
  return out;
}"""

# Heading levels in document order; a "skip" is a heading more than one level below the previous.
OUTLINE = r"""() => {
  const hs = [...document.querySelectorAll('h1,h2,h3,h4,h5,h6')].filter(h => h.getClientRects().length && !h.closest('[hidden]'));
  const levels = hs.map(h => Number(h.tagName[1]));
  const skips = [];
  for (let i = 1; i < levels.length; i++) if (levels[i] > levels[i - 1] + 1) skips.push(`${levels[i - 1]}→${levels[i]} «${hs[i].innerText.trim().slice(0, 30)}»`);
  return {h1: levels.filter(l => l === 1).length, skips};
}"""

LATIN_UNIT_IN_FA = re.compile(r"[۰-۹٫]+\s*(?:B|KB|MB|GB|TB)\b|\b(?:B|KB|MB|GB|TB)\s*[۰-۹]")


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

        def open_page(path: str, vp="m390", locale="fa", theme="light", **kw):
            ctx = make_context(browser, vp, locale, theme, **kw)
            page = ctx.new_page()
            page.goto(BASE + path, wait_until="networkidle")
            settle(page, 400)
            return ctx, page

        # 1) touch targets (plan: tapUnder44 on a phone lists only inline text links) -------------
        pages = [
            ("/", None), ("/", {"mock_state": "active"}), ("/", {"mock_state": "cooldown"}),
            ("/", {"mock_state": "exhausted"}), ("/status", {"mock_state": "active"}),
            ("/faq", None), ("/contact", None), ("/guides", None), ("/guides/android", None),
            ("/l/vpn-germany", None), ("/locations", None), ("/articles", None), ("/about", None),
            ("/privacy", None), ("/offline", None), ("/nope", None),
        ]
        # English too: Latin runs set a shorter line box, so a padded Persian link can clear 44px
        # while the same link in English falls short (the footer's did, at 42)
        for vp, locale in (("m360", "fa"), ("m390", "fa"), ("m390", "en")):
            small: dict[str, list[str]] = {}
            for path, cookies in pages:
                ctx, page = open_page(path, vp, locale, cookies=cookies)
                found = page.evaluate(SMALL_TARGETS)
                if path == "/" and not cookies:
                    page.click("button.burger")
                    page.wait_for_timeout(500)
                    found += ["[menu] " + f for f in page.evaluate(SMALL_TARGETS.replace(
                        "document.querySelectorAll(", "document.querySelector('#site-menu').querySelectorAll("))]
                if found:
                    small[f"{path} {cookies or ''}"] = found
                ctx.close()
            record(f"{vp} {locale}: no control under 44px outside running text ({len(pages)} pages + the menu)",
                   not small, small=small)

        # 2) the phone menu keeps Tab inside, locks the page, returns focus (plan) ------------------
        ctx, page = open_page("/")
        page.click("button.burger")
        page.wait_for_timeout(500)
        inside, stops = True, []
        for _ in range(24):
            page.keyboard.press("Tab")
            here = page.evaluate("(() => { const a = document.activeElement; return {inside: !!a.closest('#site-menu'), name: (a.getAttribute('aria-label') || a.innerText || '').trim().slice(0, 20)}; })()")
            inside = inside and here["inside"]
            stops.append(here["name"])
        overflow = page.evaluate("getComputedStyle(document.body).overflow")
        page.screenshot(path=str(out / "d-menu.png"))
        page.keyboard.press("Escape")
        page.wait_for_timeout(400)
        back = page.evaluate("document.activeElement?.classList.contains('burger')")
        after = page.evaluate("getComputedStyle(document.body).overflow")
        record("menu: 24 Tabs stay inside, body{overflow:hidden}, Esc returns focus to the burger",
               inside and overflow == "hidden" and back and after != "hidden",
               overflow_open=overflow, overflow_closed=after, focus_back=back, tab_stops=stops[:10])
        ctx.close()

        # 3) dialogs: named, focus in, Tab kept, Esc closes and gives focus back -------------------
        ctx, page = open_page("/status", cookies={"mock_state": "active"})
        page.click(".danger-row .btn.danger")
        page.wait_for_selector("[role=dialog][aria-labelledby]", timeout=4000)
        d = page.evaluate(
            "(() => { const dl = document.querySelector('[role=dialog][aria-labelledby=\"rm-title\"]');"
            " const name = document.getElementById(dl.getAttribute('aria-labelledby'))?.innerText;"
            " return {title: name, focusInside: dl.contains(document.activeElement), overflow: getComputedStyle(document.body).overflow}; })()"
        )
        trapped = True
        for _ in range(6):
            page.keyboard.press("Tab")
            trapped = trapped and page.evaluate("!!document.activeElement.closest('[role=dialog]')")
        page.keyboard.press("Escape")
        page.wait_for_timeout(300)
        closed = page.evaluate("!document.querySelector('[role=dialog][aria-labelledby=\"rm-title\"]')")
        back = page.evaluate("document.activeElement?.classList.contains('danger')")
        record("reset dialog: named, focus inside, Tab kept, page locked, Esc closes back to its button",
               bool(d["title"]) and d["focusInside"] and trapped and d["overflow"] == "hidden" and closed and back,
               **d, tab_trapped=trapped, closed=closed, focus_back=back)
        ctx.close()

        # 4) skip link: the first Tab stop, and it lands on <main> --------------------------------
        ctx, page = open_page("/", "d1280")
        page.keyboard.press("Tab")
        first = page.evaluate("document.activeElement?.className")
        page.keyboard.press("Enter")
        page.wait_for_timeout(300)
        landed = page.evaluate("document.activeElement?.id")
        record("skip link: first Tab stop, Enter moves focus to <main>", first == "skip-link" and landed == "main",
               first=first, landed=landed)
        ctx.close()

        # 5) live feedback: «کپی شد» reaches a live region ----------------------------------------
        ctx, page = open_page("/", cookies={"mock_state": "active"})
        ctx.grant_permissions(["clipboard-read", "clipboard-write"], origin=BASE)
        page.click(".copyfield .btn")
        page.wait_for_timeout(200)
        live = page.evaluate("[...document.querySelectorAll('.copyfield [role=status]')].map(e => e.textContent)")
        record("copy confirmation is announced (an always-mounted live region holds «کپی شد»)",
               any("کپی شد" in (x or "") for x in live), live=live)
        ctx.close()

        # 6) accordions: aria-controls to a real answer, closed answers findable ------------------
        ctx, page = open_page("/faq")
        acc = page.evaluate(
            "(() => { const heads = [...document.querySelectorAll('.acc-head')];"
            " const ok = heads.every(h => h.getAttribute('aria-controls') && document.getElementById(h.getAttribute('aria-controls')));"
            " const closed = [...document.querySelectorAll('.acc-body[hidden]')].map(b => b.getAttribute('hidden'));"
            " return {heads: heads.length, controls: ok, closed: closed.length, untilFound: closed.filter(v => v === 'until-found').length,"
            " inHeading: heads.every(h => /^H[2-4]$/.test(h.parentElement.tagName))}; })()"
        )
        record("accordion: aria-controls resolve, questions sit in headings, closed answers are hidden=until-found",
               acc["heads"] > 0 and acc["controls"] and acc["inHeading"] and acc["closed"] > 0
               and acc["untilFound"] == acc["closed"], **acc)
        ctx.close()

        # 7) heading outline: an H1 everywhere, no skipped level (04-probes §6) --------------------
        outline = {}
        for path, cookies in (("/", None), ("/offline", None), ("/contact", None), ("/guides", None),
                              ("/faq", None), ("/status", {"mock_state": "active"}),
                              ("/l/vpn-germany", None), ("/articles", None), ("/locations", None)):
            ctx, page = open_page(path, "d1280", cookies=cookies)
            o = page.evaluate(OUTLINE)
            if o["h1"] != 1 or o["skips"]:
                outline[path] = o
            ctx.close()
        record("heading outline: exactly one H1 and no skipped level on 9 pages", not outline, bad=outline)

        # 8) three-state theme: system is reachable again, and every control agrees ---------------
        ctx, page = open_page("/status", "d1280", cookies={"mock_state": "active"})
        state = (
            "(() => ({attr: document.getElementById('app').getAttribute('data-theme'),"
            " cookie: document.cookie.includes('theme='),"
            " header: document.querySelector('.hd-theme [aria-pressed=true]')?.getAttribute('aria-label'),"
            " settings: document.querySelector('.settings .mini-seg[aria-label=\"تم\"] [aria-pressed=true]')"
            "?.textContent}))()"
        )
        page.click(".settings [role=group] button:has-text('تاریک')")
        page.wait_for_timeout(200)
        dark = page.evaluate(state)
        page.click(".settings [role=group] button:has-text('سیستم')")
        page.wait_for_timeout(200)
        system = page.evaluate(state)
        pressed = page.evaluate("document.querySelector('.hd-theme [aria-pressed=true]')?.getAttribute('aria-label')")
        record("theme: dark sets the attribute + cookie; «سیستم» clears both; the header control follows",
               dark["attr"] == "dark" and dark["cookie"] and dark["header"] == "تاریک"
               and dark["settings"] == "تاریک" and system["attr"] is None and not system["cookie"]
               and pressed == "سیستم" and system["settings"] == "سیستم",
               dark=dark, system=system, header_after=pressed)
        ctx.close()

        # 9) location names in the visitor's language (plan: the English UI says «Germany») --------
        ctx, page = open_page("/", locale="en")
        names = page.evaluate("[...document.querySelectorAll('.loc-card:not([hidden]) .nm')].map(e => e.textContent)")
        page.screenshot(path=str(out / "d-en-names.png"))
        record("English UI names the locations in English", "Germany" in names and not any(
            re.search(r"[؀-ۿ]", n) for n in names), names=names)
        ctx.close()

        # 10) one volume format — no Latin unit beside Persian digits, no reversed «GB ۱» ----------
        leaks = {}
        for path, cookies in (("/", None), ("/", {"mock_state": "active"}), ("/", {"mock_state": "exhausted"}),
                              ("/status", {"mock_state": "active"}), ("/faq", {"mock_state": "active"})):
            ctx, page = open_page(path, cookies=cookies)
            text = page.evaluate("document.body.innerText")
            found = LATIN_UNIT_IN_FA.findall(text)
            if found:
                leaks[f"{path} {cookies or ''}"] = found[:5]
            ctx.close()
        ctx, page = open_page("/", cookies={"mock_state": "active"})
        fa_meter = page.evaluate("document.querySelector('.meter .v')?.innerText")
        chip = None
        ctx.close()
        ctx, page = open_page("/", locale="en")
        chip = page.evaluate("document.querySelector('.allowance')?.innerText")
        ctx.close()
        record("volumes: Persian units in Persian (no «GB ۱»), the symbol in English",
               not leaks and "گیگابایت" in (fa_meter or "") and (chip or "").strip().startswith("1 GB"),
               leaks=leaks, fa_meter=fa_meter, en_chip=chip)

        browser.close()

    (out / "accept-d.json").write_text(json.dumps(results, ensure_ascii=False, indent=1))
    failed = [r["check"] for r in results if not r["ok"]]
    print(f"\n{len(results) - len(failed)}/{len(results)} passed" + (f" — FAILED: {failed}" if failed else ""))
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
