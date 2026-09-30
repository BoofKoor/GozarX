"""Render the public site headless, screenshot it, and PROBE the result — the site's version of the
loop `docs/panel/shot.py` runs for the panel. Reading the code finds some defects; rendering finds
the rest (a unit printed ahead of its number, a skeleton that paints nothing, a tap target 32px wide).

    cd frontend/site && npm run build
    python3 docs/website/audit/mockapi.py &
    BACKEND_ORIGIN=http://127.0.0.1:8000 npx next start -p 3100 &
    python3 docs/website/audit/audit.py OUTDIR [--only NAME_SUBSTRING]

Writes OUTDIR/<name>.png for every capture and OUTDIR/probes.json with the measurements. Needs
`pip install playwright` and drives the Chromium already on the box.
"""

from __future__ import annotations

import argparse
import glob
import json
import os
import pathlib
import sys
import time

BASE = os.environ.get("SITE_BASE", "http://127.0.0.1:3100")

ANDROID_UA = (
    "Mozilla/5.0 (Linux; Android 14; Pixel 8) AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/140.0.0.0 Mobile Safari/537.36"
)
IPHONE_UA = (
    "Mozilla/5.0 (iPhone; CPU iPhone OS 18_5 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) "
    "Version/18.5 Mobile/15E148 Safari/604.1"
)

VIEWPORTS = {
    "m360": (360, 740),
    "m390": (390, 844),
    "t768": (768, 1024),
    "d1280": (1280, 800),
    "d1440": (1440, 900),
}

# ---------------------------------------------------------------------------------------------------
# probes — run inside the page. Each returns plain JSON.
# ---------------------------------------------------------------------------------------------------
PROBE_JS = r"""
() => {
  const vw = document.documentElement.clientWidth;
  const out = {};
  const vis = (el) => {
    const cs = getComputedStyle(el);
    if (cs.display === 'none' || cs.visibility === 'hidden' || +cs.opacity === 0) return false;
    const r = el.getBoundingClientRect();
    return r.width > 0 && r.height > 0;
  };
  const inHidden = (el) => { for (let e = el; e; e = e.parentElement) { const cs = getComputedStyle(e);
      if (cs.display === 'none' || cs.visibility === 'hidden') return true; } return false; };
  const label = (el) => {
    const t = (el.getAttribute('aria-label') || el.innerText || el.getAttribute('title') || el.value || '').trim().replace(/\s+/g,' ');
    const cls = (el.className && el.className.baseVal === undefined) ? String(el.className) : '';
    return `${el.tagName.toLowerCase()}${cls ? '.' + cls.split(' ').filter(Boolean).slice(0,2).join('.') : ''} «${t.slice(0,40)}»`;
  };

  // 1) horizontal overflow — the scroller AND any element poking past the viewport
  out.scrollWidth = document.scrollingElement.scrollWidth;
  out.clientWidth = vw;
  const over = [];
  for (const el of document.querySelectorAll('#app *')) {
    if (inHidden(el)) continue;
    const r = el.getBoundingClientRect();
    if (r.width === 0) continue;
    if (r.right > vw + 1 || r.left < -1) {
      // skip content inside an intended horizontal scroller
      let p = el.parentElement, clipped = false;
      while (p && p.id !== 'app') { const ox = getComputedStyle(p).overflowX; if (ox === 'auto' || ox === 'scroll' || ox === 'hidden' || ox === 'clip') { clipped = true; break; } p = p.parentElement; }
      if (!clipped) over.push(label(el) + ` [${Math.round(r.left)}→${Math.round(r.right)}]`);
    }
  }
  out.overflow = over.slice(0, 15);

  // 2) tap targets
  const small44 = [], small24 = [];
  for (const el of document.querySelectorAll('a[href], button, input, select, textarea, [role=button], [role=switch], [role=radio], summary')) {
    if (!vis(el) || inHidden(el)) continue;
    const r = el.getBoundingClientRect();
    const w = Math.round(r.width), h = Math.round(r.height);
    // inline text links inside a paragraph are exempt (WCAG 2.5.8 inline exception)
    const inline = el.tagName === 'A' && getComputedStyle(el).display === 'inline' && el.closest('p,li');
    if (inline) continue;
    if (w < 24 || h < 24) small24.push(`${label(el)} ${w}×${h}`);
    else if (w < 44 || h < 44) small44.push(`${label(el)} ${w}×${h}`);
  }
  out.tapUnder24 = small24; out.tapUnder44 = small44;

  // 3) contrast — every visible text run against its effective solid background
  const parse = (c) => { const m = c.match(/rgba?\(([^)]+)\)/); if (!m) return null; const p = m[1].split(/[ ,/]+/).filter(Boolean).map(Number); return {r:p[0], g:p[1], b:p[2], a: p.length > 3 ? p[3] : 1}; };
  const lum = ({r,g,b}) => { const f = (v) => { v/=255; return v <= .03928 ? v/12.92 : Math.pow((v+.055)/1.055, 2.4); }; return .2126*f(r)+.7152*f(g)+.0722*f(b); };
  const blend = (top, bot) => ({ r: top.r*top.a + bot.r*(1-top.a), g: top.g*top.a + bot.g*(1-top.a), b: top.b*top.a + bot.b*(1-top.a), a: 1 });
  const bgOf = (el) => {
    const layers = []; let gradient = false;
    for (let e = el; e; e = e.parentElement) {
      const cs = getComputedStyle(e);
      if (cs.backgroundImage && cs.backgroundImage !== 'none' && !e.matches('img')) gradient = true;
      const c = parse(cs.backgroundColor); if (c && c.a > 0) { layers.push(c); if (c.a >= 1) break; }
    }
    let bg = {r:255,g:255,b:255,a:1};
    const rootBg = parse(getComputedStyle(document.body).backgroundColor); if (rootBg && rootBg.a) bg = rootBg;
    for (let i = layers.length - 1; i >= 0; i--) bg = blend(layers[i], bg);
    return {bg, gradient};
  };
  const fails = []; const seen = new Set();
  const walker = document.createTreeWalker(document.getElementById('app'), NodeFilter.SHOW_TEXT);
  let n; let checked = 0;
  while ((n = walker.nextNode())) {
    const txt = n.nodeValue.trim(); if (!txt || txt.length < 1) continue;
    const el = n.parentElement; if (!el || !vis(el) || inHidden(el)) continue;
    if (el.closest('svg')) continue;
    const cs = getComputedStyle(el);
    if (cs.color === 'rgba(0, 0, 0, 0)' || cs.webkitTextFillColor === 'rgba(0, 0, 0, 0)') continue; // gradient text
    const fg = parse(cs.color); if (!fg) continue;
    const {bg, gradient} = bgOf(el);
    const fgb = fg.a < 1 ? blend(fg, bg) : fg;
    const L1 = lum(fgb), L2 = lum(bg);
    const ratio = (Math.max(L1,L2)+.05)/(Math.min(L1,L2)+.05);
    const size = parseFloat(cs.fontSize), bold = +cs.fontWeight >= 700;
    const large = size >= 24 || (size >= 18.66 && bold);
    const need = large ? 3 : 4.5;
    checked++;
    if (ratio < need) {
      const key = `${cs.color}|${txt.slice(0,20)}`; if (seen.has(key)) continue; seen.add(key);
      fails.push({ text: txt.slice(0, 50), ratio: +ratio.toFixed(2), need, size, el: label(el), gradientBg: gradient });
    }
  }
  out.contrastChecked = checked; out.contrastFails = fails.slice(0, 40);

  // 4) headings outline
  out.headings = [...document.querySelectorAll('h1,h2,h3,h4,h5,h6')].filter(vis).map(h => `${h.tagName}: ${h.innerText.trim().replace(/\s+/g,' ').slice(0,70)}`);

  // 5) images
  out.imgNoAlt = [...document.querySelectorAll('img')].filter(i => !i.hasAttribute('alt')).map(i => i.src.split('/').pop());
  out.imgNoDims = [...document.querySelectorAll('img')].filter(i => !i.getAttribute('width') && !i.style.inlineSize && !i.style.width).map(i => i.src.split('/').pop()).slice(0, 10);

  // 6) unnamed controls
  out.unnamed = [...document.querySelectorAll('a[href], button, input, select, textarea, [role=switch], [role=button]')]
    .filter(el => vis(el) && !inHidden(el))
    .filter(el => { const name = (el.getAttribute('aria-label') || el.innerText || el.getAttribute('title') || '').trim();
      const lbl = el.id && document.querySelector(`label[for="${el.id}"]`); const alt = el.querySelector('img[alt]:not([alt=""])');
      return !name && !lbl && !alt && !el.getAttribute('aria-labelledby') && !el.getAttribute('placeholder'); })
    .map(label);

  // 7) fonts actually used on key elements
  const pick = (sel) => { const e = document.querySelector(sel); return e ? getComputedStyle(e).fontFamily.split(',')[0] : null; };
  out.fonts = { body: pick('#app'), h1: pick('h1'), button: pick('button'), input: pick('input') };
  out.fontsLoaded = [...document.fonts].filter(f => f.status === 'loaded').map(f => `${f.family} ${f.weight}`);

  // 8) Latin digits in a Persian page outside technical islands
  out.lang = document.documentElement.lang; out.dir = document.documentElement.dir;
  const latin = [];
  if (document.documentElement.lang === 'fa') {
    const w2 = document.createTreeWalker(document.getElementById('app'), NodeFilter.SHOW_TEXT);
    let t;
    while ((t = w2.nextNode())) {
      const s = t.nodeValue; if (!/[0-9]/.test(s)) continue;
      const el = t.parentElement; if (!el || inHidden(el) || !vis(el)) continue;
      if (el.closest('code, [dir=ltr] code, .copyfield, .bigcode, .id-code, input, textarea, script, style')) continue;
      latin.push(`${label(el)}: «${s.trim().slice(0,50)}»`);
    }
  }
  out.latinDigitsInFa = [...new Set(latin)].slice(0, 30);

  // 9) landmarks + skip link
  out.landmarks = { header: !!document.querySelector('header'), nav: document.querySelectorAll('nav').length, main: !!document.querySelector('main'), footer: !!document.querySelector('footer') };
  const first = document.querySelector('a[href^="#"]'); out.firstInPageLink = first ? first.getAttribute('href') : null;

  // 10) stuff the reveal observer may have left invisible
  out.stillHiddenReveals = [...document.querySelectorAll('.reveal')].filter(e => getComputedStyle(e).opacity === '0').length;
  return out;
}
"""


def find_chrome() -> str | None:
    for pattern in (
        os.environ.get("SITE_CHROME", ""),
        f"{os.environ.get('PLAYWRIGHT_BROWSERS_PATH', '/opt/pw-browsers')}/chromium-*/chrome-linux/chrome",
    ):
        if pattern:
            hit = sorted(glob.glob(pattern))
            if hit:
                return hit[-1]
    return None


def make_context(browser, vp="m390", locale="fa", theme="light", ua="android", motion="reduce",
                 cookies=None, scheme=None):
    w, h = VIEWPORTS[vp]
    mobile = vp.startswith("m")
    opts = dict(viewport={"width": w, "height": h}, device_scale_factor=2 if mobile else 1,
                reduced_motion=motion, color_scheme=scheme or (theme if theme in ("light", "dark") else "light"),
                locale="fa-IR" if locale == "fa" else "en-US")
    if mobile:
        opts.update(is_mobile=True, has_touch=True, user_agent=IPHONE_UA if ua == "ios" else ANDROID_UA)
    ctx = browser.new_context(**opts)
    jar = [{"name": "locale", "value": locale, "url": BASE}]
    if theme in ("light", "dark"):
        jar.append({"name": "theme", "value": theme, "url": BASE})
    for k, v in (cookies or {}).items():
        jar.append({"name": k, "value": v, "url": BASE})
    ctx.add_cookies(jar)
    return ctx


def settle(page, ms=900):
    page.wait_for_load_state("networkidle")
    try:
        page.evaluate("document.fonts.ready")
    except Exception:
        pass
    page.wait_for_timeout(ms)
    # A full-page capture never scrolls, so the IntersectionObserver never marks the sections below
    # the fold `.in` — and under reduced motion they stay at opacity 0 anyway, because the duplicate
    # `#app.reveal-js .reveal` rule at globals.css:779 outranks the reduced-motion override at :503
    # (a real bug, reported as V-finding). Count them for the probe, then reveal them for the shot.
    page.evaluate("window.__hiddenReveals = [...document.querySelectorAll('.reveal')]"
                  ".filter(e => getComputedStyle(e).opacity === '0').length")
    page.evaluate("document.querySelectorAll('.reveal').forEach(e => e.classList.add('in'))")
    page.wait_for_timeout(150)


# ---------------------------------------------------------------------------------------------------
# actions — the states a URL alone cannot reach
# ---------------------------------------------------------------------------------------------------
def act_claim(page):
    page.click("button.cta")
    page.wait_for_selector(".cfg", timeout=8000)
    page.wait_for_timeout(700)


def act_claim_midflight(page):
    page.click("button.cta")
    page.wait_for_timeout(250)  # the mock holds /claim ~900ms — capture the provisioning state


def act_claim_outcome(page):
    page.click("button.cta")
    page.wait_for_timeout(1800)


def act_change_loc(page):
    page.click("button.chg-btn")
    page.wait_for_timeout(500)


def act_menu(page):
    page.click("button.burger")
    page.wait_for_timeout(500)


def act_transfer(page):
    page.click(".transfer-card button.btn.block")
    page.wait_for_timeout(600)


def act_reset_dialog(page):
    page.click(".danger-row button")
    page.wait_for_timeout(400)


def act_push_prompt(page):
    page.locator(".rw2-row", has_text="اعلان").first.click()
    page.wait_for_timeout(400)


def act_ios_steps(page):
    page.locator(".rw2-row", has_text="وب‌اپ").first.click()
    page.wait_for_timeout(400)


def act_faq_empty(page):
    page.fill(".idx-search input", "zzzz")
    page.wait_for_timeout(300)


def act_contact_err(page):
    page.click("form.form-card button.cta")
    page.wait_for_timeout(300)


def act_contact_sent(page):
    page.fill("#c-msg", "سلام، کانفیگ آلمان وصل نمی‌شود.")
    page.click("form.form-card button.cta")
    page.wait_for_timeout(900)


def act_restore_bad(page):
    page.fill(".code-input input", "abcd-efgh")
    page.click(".code-input button")
    page.wait_for_timeout(700)


def act_scroll_hero_bottom(page):
    page.evaluate("window.scrollTo(0, 0)")


# name, path, vp, locale, theme, extra
J = []


def job(name, path, vp="m390", locale="fa", theme="light", shot="full", ua="android", cookies=None,
        action=None, probe=False, motion="reduce", scheme=None, wait=900):
    J.append(dict(name=name, path=path, vp=vp, locale=locale, theme=theme, shot=shot, ua=ua,
                  cookies=cookies or {}, action=action, probe=probe, motion=motion, scheme=scheme,
                  wait=wait))


# homepage — the matrix
for vp in ("m360", "m390", "t768", "d1280"):
    for th in ("light", "dark"):
        job(f"home-fa-{th}-{vp}", "/", vp=vp, theme=th, probe=(th == "light"))
job("home-en-light-m390", "/", locale="en", probe=True)
job("home-en-dark-d1280", "/", vp="d1280", locale="en", theme="dark", probe=True)
job("home-fa-fold-m360", "/", vp="m360", shot="viewport")
job("home-fa-fold-m390", "/", shot="viewport")
job("home-fa-fold-d1280", "/", vp="d1280", shot="viewport")
job("home-fa-fold-d1280-dark", "/", vp="d1280", theme="dark", shot="viewport")
job("home-en-fold-m390", "/", locale="en", shot="viewport")
job("home-fa-auto-dark-m390", "/", theme="auto", scheme="dark", shot="viewport")

# claim widget — every state (element capture of the hero widget)
W = "#hero-widget"
job("w-s1-idle-fa-light", "/", shot=W)
job("w-s1-idle-fa-dark", "/", theme="dark", shot=W)
job("w-s1-idle-en-light", "/", locale="en", shot=W)
job("w-s1-idle-en-names", "/", locale="en", shot=W, cookies={"mock_locs": "en"})
job("w-loading-fa-light", "/", shot=W, cookies={"mock_delay": "20000"}, wait=1500)
job("w-s2-provisioning-fa", "/", shot=W, action=act_claim_midflight)
job("w-s3-fresh-fa-light", "/", shot=W, action=act_claim)
job("w-s3-fresh-fa-dark", "/", theme="dark", shot=W, action=act_claim)
job("w-s3-fresh-en-light", "/", locale="en", shot=W, action=act_claim)
job("w-s3-fresh-fa-ios", "/", shot=W, ua="ios", action=act_claim)
job("w-s3-fresh-fa-desktop", "/", vp="d1280", shot=W, action=act_claim)
job("w-s4-active-fa-light", "/", shot=W, cookies={"mock_state": "active"})
job("w-s4-active-fa-dark", "/", theme="dark", shot=W, cookies={"mock_state": "active"})
job("w-s4-active-en-light", "/", locale="en", shot=W, cookies={"mock_state": "active"})
job("w-s4-change-loc-fa", "/", shot=W, cookies={"mock_state": "active"}, action=act_change_loc)
job("w-s5-cooldown-fa-light", "/", shot=W, cookies={"mock_state": "cooldown"})
job("w-s5-cooldown-fa-dark", "/", theme="dark", shot=W, cookies={"mock_state": "cooldown"})
job("w-s5-cooldown0-fa", "/", shot=W, cookies={"mock_state": "cooldown0"}, wait=4000)
job("w-s6-exhausted-fa-light", "/", shot=W, cookies={"mock_state": "exhausted"})
job("w-s6-exhausted-fa-dark", "/", theme="dark", shot=W, cookies={"mock_state": "exhausted"})
job("w-s7-nolocs-fa", "/", shot=W, cookies={"mock_locs": "none"})
job("w-s8-error-fa", "/", shot=W, cookies={"mock_state": "error"})
job("w-out-not-ready-fa", "/", shot=W, cookies={"mock_claim": "not_ready"}, action=act_claim_outcome)
job("w-out-rate-limited-fa", "/", shot=W, cookies={"mock_claim": "rate_limited"}, action=act_claim_outcome)
job("w-out-loc-unavail-fa", "/", shot=W, cookies={"mock_claim": "location_unavailable"}, action=act_claim_outcome)
job("w-few-locs-fa", "/", shot=W, cookies={"mock_locs": "few"})

# full homepage in the delivered state (how tall does the page get, what sits under it)
job("home-fa-active-m390", "/", cookies={"mock_state": "active"})

# status / account page
job("status-active-fa-light-m390", "/status", cookies={"mock_state": "active"}, probe=True)
job("status-active-fa-dark-m390", "/status", theme="dark", cookies={"mock_state": "active"})
job("status-active-fa-light-d1280", "/status", vp="d1280", cookies={"mock_state": "active"}, probe=True)
job("status-active-en-light-d1280", "/status", vp="d1280", locale="en", cookies={"mock_state": "active"})
job("status-new-fa-light-m390", "/status", cookies={"mock_state": "new", "mock_hist": "0"})
job("status-cooldown-fa-dark-d1280", "/status", vp="d1280", theme="dark", cookies={"mock_state": "cooldown"})
job("status-loading-fa-m390", "/status", cookies={"mock_delay": "20000"}, shot="viewport", wait=1500)
job("status-transfer-fa-m390", "/status", cookies={"mock_state": "active"}, action=act_transfer, shot="#transfer")
job("status-restore-bad-fa-m390", "/status", cookies={"mock_state": "active"}, action=act_restore_bad, shot="#transfer")
job("status-reset-dialog-fa-m390", "/status", cookies={"mock_state": "active"}, action=act_reset_dialog, shot="viewport")
job("status-push-prompt-fa-m390", "/status", cookies={"mock_state": "active"}, action=act_push_prompt, shot="viewport")
job("status-ios-steps-fa-m390", "/status", ua="ios", cookies={"mock_state": "active"}, action=act_ios_steps, shot="viewport")
job("status-rewards-fa-light", "/status", cookies={"mock_state": "active"}, shot=".rewards-card")
job("status-rewards-en-light", "/status", locale="en", cookies={"mock_state": "active"}, shot=".rewards-card")

# locations / landings
job("locations-fa-light-m390", "/locations", probe=True)
job("locations-fa-light-d1280", "/locations", vp="d1280")
job("locations-en-light-d1280", "/locations", vp="d1280", locale="en")
job("landing-germany-fa-m390", "/l/vpn-germany", probe=True)
job("landing-germany-fa-d1280", "/l/vpn-germany", vp="d1280")
job("landing-v2ray-fa-m390", "/l/free-v2ray-config")
job("landing-germany-en-d1280", "/l/vpn-germany", vp="d1280", locale="en")
job("landing-germany-fa-fold-m390", "/l/vpn-germany", shot="viewport")

# guides / faq / contact / about / legal / system
job("guides-fa-light-m390", "/guides", probe=True)
job("guides-fa-dark-d1280", "/guides", vp="d1280", theme="dark")
job("guides-en-light-d1280", "/guides", vp="d1280", locale="en")
job("guide-android-fa-m390", "/guides/android", probe=True)
job("guide-windows-en-d1280", "/guides/windows", vp="d1280", locale="en")
job("faq-fa-light-m390", "/faq", probe=True)
job("faq-fa-empty-m390", "/faq", action=act_faq_empty, shot="viewport")
job("faq-en-dark-d1280", "/faq", vp="d1280", locale="en", theme="dark")
job("contact-fa-light-m390", "/contact", probe=True)
job("contact-fa-err-m390", "/contact", action=act_contact_err, shot="form.form-card")
job("contact-fa-sent-m390", "/contact", action=act_contact_sent, shot="form.form-card")
job("contact-fa-light-d1280", "/contact", vp="d1280")
job("about-fa-light-m390", "/about", probe=True)
job("about-en-dark-d1280", "/about", vp="d1280", locale="en", theme="dark")
job("privacy-fa-light-m390", "/privacy", probe=True)
job("terms-en-light-d1280", "/terms", vp="d1280", locale="en")
job("offline-fa-light-m390", "/offline", probe=True)
job("notfound-fa-light-m390", "/this-page-does-not-exist", probe=True)
job("notfound-en-dark-d1280", "/nope", vp="d1280", locale="en", theme="dark")

# chrome
job("menu-open-fa-light-m390", "/", action=act_menu, shot="viewport")
job("menu-open-fa-dark-m390", "/", theme="dark", action=act_menu, shot="viewport")
job("menu-open-en-light-m390", "/", locale="en", action=act_menu, shot="viewport")
job("header-fa-d1280", "/faq", vp="d1280", shot="header.hd")
job("header-en-d1280", "/faq", vp="d1280", locale="en", shot="header.hd")
job("footer-fa-m390", "/faq", shot="footer.ft")
job("footer-fa-d1280", "/faq", vp="d1280", shot="footer.ft")


def run(outdir: pathlib.Path, only: str | None) -> int:
    from playwright.sync_api import sync_playwright

    chrome = find_chrome()
    results = {}
    outdir.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as p:
        browser = p.chromium.launch(executable_path=chrome, args=["--font-render-hinting=none"])
        for j in J:
            if only and only not in j["name"]:
                continue
            t0 = time.time()
            ctx = make_context(browser, j["vp"], j["locale"], j["theme"], j["ua"], j["motion"],
                               j["cookies"], j["scheme"])
            page = ctx.new_page()
            errors = []
            page.on("console", lambda m: errors.append(f"{m.type}: {m.text[:160]}") if m.type in ("error", "warning") else None)
            page.on("pageerror", lambda e: errors.append(f"pageerror: {str(e)[:160]}"))
            try:
                page.goto(BASE + j["path"], wait_until="domcontentloaded")
                if j["cookies"].get("mock_delay"):
                    page.wait_for_timeout(j["wait"])
                else:
                    settle(page, j["wait"])
                if j["action"]:
                    j["action"](page)
                target = outdir / f"{j['name']}.png"
                if j["shot"] == "full":
                    page.screenshot(path=str(target), full_page=True)
                elif j["shot"] == "viewport":
                    page.screenshot(path=str(target))
                else:
                    page.locator(j["shot"]).first.screenshot(path=str(target))
                rec = {"errors": errors}
                if j["probe"]:
                    rec["probe"] = page.evaluate(PROBE_JS)
                results[j["name"]] = rec
                print(f"ok  {j['name']}  ({time.time()-t0:.1f}s)")
            except Exception as e:  # keep going — one broken capture must not hide the rest
                results[j["name"]] = {"failed": str(e)[:300], "errors": errors}
                print(f"ERR {j['name']}: {str(e)[:200]}")
            finally:
                ctx.close()
        browser.close()
    prev = {}
    pj = outdir / "probes.json"
    if pj.exists() and only:
        prev = json.loads(pj.read_text())
    prev.update(results)
    pj.write_text(json.dumps(prev, ensure_ascii=False, indent=1))
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("outdir")
    ap.add_argument("--only", default=None, help="run only jobs whose name contains this")
    ap.add_argument("--list", action="store_true")
    args = ap.parse_args()
    if args.list:
        print("\n".join(j["name"] for j in J))
        return 0
    return run(pathlib.Path(args.outdir), args.only)


if __name__ == "__main__":
    sys.exit(main())
