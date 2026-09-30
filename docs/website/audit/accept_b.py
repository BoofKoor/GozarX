"""Phase B acceptance, driven against the built site + mockapi.py — the claim flow's behaviour over
TIME, which a screenshot cannot show: every claim outcome lands on its own screen, a cooldown that
runs out comes back by itself, a revive is celebrated without a refresh, and the picker is one Tab
stop. Needs the same setup as audit.py:

    cd frontend/site && npm run build
    python3 docs/website/audit/mockapi.py &
    BACKEND_ORIGIN=http://127.0.0.1:8000 npx next start -p 3100 &
    python3 docs/website/audit/accept_b.py OUTDIR

Writes OUTDIR/accept-b.json and one screenshot per check; exits non-zero if any check fails. The
widget roots carry `data-view` (s1 · s3 · s4 · rv · s5 · s6 · s7 · s7x · s8 · sb) and an inline
notice carries `data-notice`, so the checks name states, not copy.
"""

from __future__ import annotations

import json
import pathlib
import sys
import time

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from audit import BASE, find_chrome, make_context  # noqa: E402

# mock_claim value → what the widget must show afterwards
OUTCOMES = {
    "ok": ("view", "s3"),
    "not_ready": ("view", "s7x"),
    "no_locations": ("view", "s7x"),
    "location_unavailable": ("notice", "loc_gone"),
    "rate_limited": ("notice", "busy"),  # refused twice: after the one automatic retry
    "rate_limited_once": ("view", "s3"),  # refused once: the automatic retry succeeds
    "turnstile_failed": ("notice", "ts"),
    "panel_error": ("view", "s8"),
    "blocked": ("view", "sb"),  # blocked while the picker sat open: not an error to retry
}


def view(page) -> str | None:
    return page.evaluate("document.querySelector('[data-view]')?.dataset.view ?? null")


def wait_for(page, predicate, timeout_s: float, poll_ms: int = 250):
    start = time.time()
    while time.time() - start < timeout_s:
        value = predicate()
        if value:
            return value, time.time() - start
        page.wait_for_timeout(poll_ms)
    return None, time.time() - start


def main() -> int:
    out = pathlib.Path(sys.argv[1] if len(sys.argv) > 1 else ".")
    out.mkdir(parents=True, exist_ok=True)
    from playwright.sync_api import sync_playwright

    results: list[dict] = []

    def record(name: str, ok: bool, **detail) -> None:
        results.append({"check": name, "ok": ok, **detail})
        print(f"{'PASS' if ok else 'FAIL'}  {name}  {json.dumps(detail, ensure_ascii=False)}")

    with sync_playwright() as p:
        browser = p.chromium.launch(executable_path=find_chrome())

        # 1) every claim outcome has its own screen ------------------------------------------------
        for outcome, (kind, want) in OUTCOMES.items():
            ctx = make_context(browser, "m390", "fa", "light", cookies={"mock_claim": outcome})
            page = ctx.new_page()
            page.goto(BASE + "/", wait_until="networkidle")
            page.wait_for_selector("[data-view='s1'] button.cta:not([disabled])", timeout=8000)
            page.click("[data-view='s1'] button.cta")
            if kind == "view":
                got, secs = wait_for(page, lambda: view(page) == want and want, 12)
            else:
                got, secs = wait_for(
                    page,
                    lambda: page.evaluate(
                        "document.querySelector('[data-notice]')?.dataset.notice ?? null"
                    )
                    == want
                    and want,
                    12,
                )
            page.wait_for_timeout(300)
            page.screenshot(path=str(out / f"b-outcome-{outcome}.png"))
            record(f"outcome:{outcome}", bool(got), expect=f"{kind}={want}", view=view(page),
                   seconds=round(secs, 1))
            ctx.close()

        # 2) a cooldown that runs out comes back to S1 by itself (mock: 20s window) ----------------
        ctx = make_context(browser, "m390", "fa", "light", cookies={"mock_state": "cooldown0"})
        page = ctx.new_page()
        page.goto(BASE + "/", wait_until="networkidle")
        page.wait_for_selector("[data-view='s5']", timeout=8000)
        got, secs = wait_for(page, lambda: view(page) == "s1", 60, poll_ms=500)
        announced = page.evaluate("document.querySelector('.sr-only[role=status]')?.textContent")
        page.screenshot(path=str(out / "b-cooldown0-after.png"))
        record("cooldown0 → s1 within 60s", bool(got), seconds=round(secs, 1), announced=announced)
        ctx.close()

        # 2b) a blocked device: its own screen, no countdown to a claim that will never come, and
        #     no reward missions that the server would refuse -----------------------------------
        ctx = make_context(browser, "m390", "fa", "light", cookies={"mock_state": "blocked"})
        page = ctx.new_page()
        page.goto(BASE + "/status", wait_until="networkidle")
        page.wait_for_selector("[data-view]:not([data-view='loading'])", timeout=8000)
        page.wait_for_timeout(400)
        probe = page.evaluate(
            """() => ({
              view: document.querySelector('[data-view]')?.dataset.view ?? null,
              countdown: !!document.querySelector('[data-view] .cd'),
              contact: document.querySelector('[data-view] a[href="/contact"]') !== null,
              rewards: !!document.querySelector('.rewards-card'),
            })"""
        )
        page.screenshot(path=str(out / "b-blocked.png"))
        record(
            "blocked → sb, no countdown, no missions",
            probe["view"] == "sb" and not probe["countdown"] and probe["contact"]
            and not probe["rewards"],
            **probe,
        )
        ctx.close()

        # 3) S6 celebrates a revive without a refresh (the page polls every 25s while visible) -----
        ctx = make_context(browser, "m390", "fa", "light", cookies={"mock_state": "exhausted"})
        page = ctx.new_page()
        page.goto(BASE + "/", wait_until="networkidle")
        page.wait_for_selector("[data-view='s6']", timeout=8000)
        page.screenshot(path=str(out / "b-revive-before.png"))
        ctx.add_cookies([{"name": "mock_state", "value": "active", "url": BASE}])
        got, secs = wait_for(page, lambda: view(page) == "rv", 40, poll_ms=500)
        note = page.evaluate("document.querySelector('.revived-note')?.textContent ?? null")
        announced = page.evaluate("document.querySelector('.sr-only[role=status]')?.textContent")
        page.screenshot(path=str(out / "b-revive-after.png"))
        record("s6 → revived without refresh", bool(got), seconds=round(secs, 1), note=note,
               announced=announced)
        ctx.close()

        # 4) keyboard: the picker is ONE Tab stop, arrows move the choice, End opens the rest ------
        ctx = make_context(browser, "m390", "fa", "light")
        page = ctx.new_page()
        page.goto(BASE + "/", wait_until="networkidle")
        page.wait_for_selector("[data-view='s1'] button.cta:not([disabled])", timeout=8000)
        presses, reached = 0, False
        for presses in range(1, 41):
            page.keyboard.press("Tab")
            if page.evaluate("document.activeElement?.classList.contains('cta')"):
                reached = True
                break
        record("Tab to the claim CTA ≤ 12", reached and presses <= 12, presses=presses)
        page.focus("[data-view='s1'] .loc-card[tabindex='0']")
        before = page.evaluate("document.activeElement.textContent")
        page.keyboard.press("ArrowLeft")  # RTL: left is forward
        page.wait_for_timeout(100)
        after = page.evaluate("document.activeElement.textContent")
        checked = page.evaluate(
            "document.querySelector('.loc-card[aria-checked=true]')?.textContent"
        )
        stops = page.evaluate("document.querySelectorAll('.loc-card[tabindex=\"0\"]').length")
        page.keyboard.press("End")
        page.wait_for_timeout(200)
        hidden = page.evaluate("document.querySelectorAll('.loc-card[hidden]').length")
        record(
            "radiogroup: arrow moves + checks, one tab stop, End reveals all",
            before != after and checked == after and stops == 1 and hidden == 0,
            before=before, after=after, checked=checked, tab_stops=stops, hidden_after_end=hidden,
        )
        ctx.close()

        # 5) switching location: explicit choice, "switch to …", cancel, «فعلی» ---------------------
        ctx = make_context(browser, "m390", "fa", "light", cookies={"mock_state": "active"})
        page = ctx.new_page()
        page.goto(BASE + "/", wait_until="networkidle")
        page.wait_for_selector("[data-view='s4'] .chg-btn", timeout=8000)
        page.click(".chg-btn")
        page.wait_for_selector(".loc-now", timeout=4000)
        idle_disabled = page.evaluate("document.querySelector('button.cta').disabled")
        reassure = page.evaluate("!!document.querySelector('[data-view=s4] .reassure')")
        page.click(".loc-card:not([hidden]) >> nth=1")
        label = page.evaluate("document.querySelector('button.cta').textContent.trim()")
        page.screenshot(path=str(out / "b-change-location.png"))
        page.click("button.cta")
        got, secs = wait_for(page, lambda: view(page) == "s4" and not page.query_selector(".loc-now"), 8)
        record(
            "change location: needs a pick, names it, no reassurance row, completes",
            idle_disabled and not reassure and label.startswith("تغییر به") and bool(got),
            disabled_before_pick=idle_disabled, reassurance_row=reassure, label=label,
        )
        ctx.close()

        # 6) the CTA explains its waits: a security check before a token exists, and a slow panel
        ctx = make_context(browser, "m390", "fa", "light", cookies={"mock_turnstile": "1"})
        page = ctx.new_page()
        page.goto(BASE + "/", wait_until="domcontentloaded")
        page.wait_for_selector("[data-view='s1'] button.cta", timeout=8000)
        busy = page.evaluate(
            "(() => { const b = document.querySelector('button.cta');"
            " return {disabled: b.disabled, busy: b.getAttribute('aria-busy'),"
            " spinner: !!b.querySelector('.spinner')}; })()"
        )
        record("CTA says it is running the security check before a token exists",
               busy["disabled"] and busy["busy"] == "true" and busy["spinner"], **busy)
        ctx.close()

        ctx = make_context(browser, "m390", "fa", "light", cookies={"mock_claim_ms": "5000"})
        page = ctx.new_page()
        page.goto(BASE + "/", wait_until="networkidle")
        page.wait_for_selector("[data-view='s1'] button.cta:not([disabled])", timeout=8000)
        page.click("button.cta")
        page.wait_for_timeout(1000)
        early = page.evaluate("document.querySelector('button.cta').textContent.trim()")
        page.wait_for_timeout(2600)
        late = page.evaluate("document.querySelector('button.cta').textContent.trim()")
        opacity = page.evaluate("getComputedStyle(document.querySelector('button.cta')).opacity")
        page.screenshot(path=str(out / "b-slow-claim.png"))
        record("a slow claim says so after 3s, at full opacity", early != late and opacity == "1",
               at_1s=early, at_3_6s=late, opacity=opacity)
        ctx.close()

        browser.close()

    (out / "accept-b.json").write_text(json.dumps(results, ensure_ascii=False, indent=1))
    failed = [r["check"] for r in results if not r["ok"]]
    print(f"\n{len(results) - len(failed)}/{len(results)} passed" + (f" — FAILED: {failed}" if failed else ""))
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
