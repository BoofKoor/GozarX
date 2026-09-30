"""Dynamic probes `audit.py` cannot take from a still page: keyboard order, layout shift while the
data loads, and what a first visit downloads. Same setup as audit.py (mock API + `next start`).

    python3 docs/website/audit/probe_extra.py OUTDIR
"""

from __future__ import annotations

import json
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).parent))
from audit import BASE, find_chrome, make_context  # noqa: E402

TAB_JS = r"""
() => {
  const el = document.activeElement;
  if (!el || el === document.body) return null;
  const r = el.getBoundingClientRect();
  const cs = getComputedStyle(el);
  const name = (el.getAttribute('aria-label') || el.innerText || el.value || '').trim().replace(/\s+/g,' ').slice(0,40);
  const ring = cs.outlineStyle !== 'none' && parseFloat(cs.outlineWidth) > 0 || cs.boxShadow !== 'none';
  const offscreen = r.bottom < 0 || r.top > innerHeight || r.right < 0 || r.left > innerWidth || cs.visibility === 'hidden';
  return `${el.tagName.toLowerCase()}${el.className && typeof el.className === 'string' ? '.' + el.className.split(' ')[0] : ''} «${name}» ring=${ring} ${offscreen ? 'OFFSCREEN' : ''}`;
}
"""

CLS_JS = r"""
() => new Promise((resolve) => {
  let cls = 0; const shifts = [];
  new PerformanceObserver((list) => {
    for (const e of list.getEntries()) {
      if (e.hadRecentInput) continue;
      cls += e.value;
      shifts.push({ value: +e.value.toFixed(4), t: Math.round(e.startTime),
        sources: (e.sources || []).map(s => s.node ? (s.node.className || s.node.nodeName).toString().slice(0, 40) : '?').slice(0, 3) });
    }
  }).observe({ type: 'layout-shift', buffered: true });
  setTimeout(() => resolve({ cls: +cls.toFixed(4), shifts }), 5000);
})
"""


def main() -> int:
    out = pathlib.Path(sys.argv[1] if len(sys.argv) > 1 else ".")
    out.mkdir(parents=True, exist_ok=True)
    from playwright.sync_api import sync_playwright

    res: dict = {}
    with sync_playwright() as p:
        browser = p.chromium.launch(executable_path=find_chrome())

        # 1) keyboard: how many Tab presses from the top of the page to the claim CTA
        for vp in ("m390", "d1280"):
            ctx = make_context(browser, vp=vp)
            page = ctx.new_page()
            page.goto(BASE + "/", wait_until="networkidle")
            page.wait_for_timeout(800)
            stops = []
            for _ in range(45):
                page.keyboard.press("Tab")
                d = page.evaluate(TAB_JS)
                stops.append(d)
                if d and "دریافت کانفیگ" in d and "cta" in d:
                    break
            res[f"tab-to-cta-{vp}"] = {"presses": len(stops), "stops": stops}
            ctx.close()

        # 1b) keyboard inside the open mobile menu: does Tab stay in the sheet?
        ctx = make_context(browser, vp="m390")
        page = ctx.new_page()
        page.goto(BASE + "/", wait_until="networkidle")
        page.click("button.burger")
        page.wait_for_timeout(400)
        res["menu-focus-after-open"] = page.evaluate(TAB_JS)
        seq = []
        for _ in range(12):
            page.keyboard.press("Tab")
            seq.append(page.evaluate(TAB_JS))
        res["menu-tab-sequence"] = seq
        res["menu-body-scroll-locked"] = page.evaluate("getComputedStyle(document.body).overflow")
        ctx.close()

        # 2) layout shift while /status is slow (1.5s) — the real-world first visit on a slow link
        for vp in ("m390", "d1280"):
            for path in ("/", "/status", "/l/vpn-germany"):
                ctx = make_context(browser, vp=vp, motion="no-preference", cookies={"mock_delay": "1500"})
                page = ctx.new_page()
                page.goto(BASE + path, wait_until="domcontentloaded")
                res[f"cls-{vp}-{path}"] = page.evaluate(CLS_JS)
                ctx.close()

        # 3) first-visit weight (mobile, homepage)
        ctx = make_context(browser, vp="m390")
        page = ctx.new_page()
        sizes: dict[str, int] = {}
        count: dict[str, int] = {}

        def on_response(r):
            try:
                body = r.body()
            except Exception:
                return
            ct = (r.headers.get("content-type") or "").split(";")[0]
            kind = ("js" if "javascript" in ct else "css" if "css" in ct else "font" if "font" in ct or r.url.endswith(".woff2")
                    else "img" if ct.startswith("image") else "html" if "html" in ct else "json" if "json" in ct else ct or "other")
            sizes[kind] = sizes.get(kind, 0) + len(body)
            count[kind] = count.get(kind, 0) + 1

        page.on("response", on_response)
        page.goto(BASE + "/", wait_until="networkidle")
        page.wait_for_timeout(1500)
        res["weight-home-m390"] = {k: {"bytes_uncompressed": v, "requests": count[k]} for k, v in sizes.items()}
        ctx.close()
        browser.close()

    (out / "probes-extra.json").write_text(json.dumps(res, ensure_ascii=False, indent=1))
    print(json.dumps(res, ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
