"""Render the built panel headless and write PNGs — the half of the loop `mockapi.py` does not do.

`README.md` used to hand out a raw `chromium --headless --screenshot` line. It works at desktop
widths and lies at every other size: **this Chromium refuses a window narrower than ~500 CSS px**.
`--window-size=360,800` lays the page out at `innerWidth = 500` and then crops the capture to 360,
so a page that reflows perfectly at 360 screenshots as if it were overflowing — a defect that does
not exist, reported by the tool that was supposed to catch defects. Verified: 360 → 500, 420 → 500,
500 → 500; the same page in a real 360-wide context has `document.scrollWidth === 360`.

It also cannot capture a recharts chart. recharts animates its series with `requestAnimationFrame`
through react-smooth, growing a clip rect from zero width; under `--virtual-time-budget` that
animation never ticks, so the `<path>` is in the DOM with correct geometry and NOTHING is painted.
Every recharts chart screenshots as an empty grid. (The panel now disables those animations under
`prefers-reduced-motion`, which this script sets — so charts render here, and an operator who asked
their OS for less motion gets a still chart rather than a spinning one.)

A browser context sets the viewport directly and waits for the page instead of racing a clock, so
both problems go away.

    cd frontend/admin && npm run build
    python3 docs/panel/mockapi.py &
    python3 docs/panel/shot.py out/ --width 360 --theme dark --locale fa / users broadcast

Needs `pip install playwright`; it drives the Chromium already on the box (PLAYWRIGHT_BROWSERS_PATH,
or --chrome). Routes are panel paths without the `/admin` prefix — `/` is the dashboard. Add
`?fill=<name>` to a route to run one of `mockapi.FILLS` first.
"""
from __future__ import annotations

import argparse
import glob
import os
import pathlib
import sys

DEFAULT_BASE = "http://127.0.0.1:4174/admin"


def find_chrome() -> str | None:
    """The pre-installed Chromium, wherever this box keeps it."""
    for pattern in (
        os.environ.get("PANEL_CHROME", ""),
        f"{os.environ.get('PLAYWRIGHT_BROWSERS_PATH', '/opt/pw-browsers')}/chromium-*/chrome-linux/chrome",
        "/usr/bin/chromium",
        "/usr/bin/chromium-browser",
        "/usr/bin/google-chrome",
    ):
        if not pattern:
            continue
        hit = sorted(glob.glob(pattern))
        if hit:
            return hit[-1]
    return None


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("outdir")
    ap.add_argument("routes", nargs="+", help="panel paths without /admin, e.g. / users site/stats")
    ap.add_argument("--width", type=int, default=1440)
    ap.add_argument("--height", type=int, default=1000)
    ap.add_argument("--theme", default="dark", choices=["dark", "light"])
    ap.add_argument("--locale", default="fa", choices=["fa", "en"])
    ap.add_argument("--base", default=DEFAULT_BASE)
    ap.add_argument("--chrome", default=None, help="path to a Chromium binary")
    ap.add_argument("--full-page", action="store_true", help="capture past the fold")
    ap.add_argument("--settle-ms", type=int, default=2500, help="wait after load, for queries + charts")
    args = ap.parse_args()

    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("shot.py needs Playwright:  pip install playwright", file=sys.stderr)
        return 2

    chrome = args.chrome or find_chrome()
    if not chrome:
        print("no Chromium found — pass --chrome /path/to/chrome", file=sys.stderr)
        return 2

    out = pathlib.Path(args.outdir)
    out.mkdir(parents=True, exist_ok=True)

    with sync_playwright() as p:
        browser = p.chromium.launch(executable_path=chrome, args=["--no-sandbox"])
        # Reduced motion stills the entry animations AND the chart animations, so a capture shows
        # the settled state rather than whatever frame the clock happened to stop on.
        ctx = browser.new_context(
            viewport={"width": args.width, "height": args.height},
            device_scale_factor=2,
            reduced_motion="reduce",
        )
        page = ctx.new_page()
        for route in args.routes:
            path, _, query = route.lstrip("/").partition("?")
            sep = "&" if query else ""
            url = f"{args.base}/{path}?{query}{sep}theme={args.theme}&locale={args.locale}"
            page.goto(url, wait_until="networkidle")
            page.wait_for_timeout(args.settle_ms)
            name = (path or "index").replace("/", "-").replace("?", "-")
            dest = out / f"{name}-{args.theme}-{args.locale}-{args.width}.png"
            page.screenshot(path=str(dest), full_page=args.full_page)
            overflow = page.evaluate("document.documentElement.scrollWidth - innerWidth")
            flag = f"  ⚠ overflows by {overflow}px" if overflow > 1 else ""
            print(f"{dest}{flag}")
        browser.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
