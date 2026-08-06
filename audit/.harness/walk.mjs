// Phase 1 walkthrough harness — READ-ONLY. Drives the built site the way a first-time Iranian user
// on a mid-range Android would, one step at a time, and records at every step: what is on screen,
// what is above the fold, how many taps it cost, and how long the UI sat before answering.
//
// Unlike Phase 0's capture.mjs (a state matrix), this walks FLOWS. Every screenshot is a step in a
// journey, named `w-<flow><NN>-<slug>.png`, and every step also emits a JSON probe so a claim in
// the report can point at a measurement rather than at a memory.
//
// Same two anti-artifact rules as Phase 0: settle the reveal observer before shooting, and wait for
// document.fonts.ready — otherwise the shots record opacity:0 sections and FOIT.

import { chromium } from "playwright";
import { mkdir, writeFile } from "node:fs/promises";

const SITE = "http://127.0.0.1:3100";
const MOCK = "http://127.0.0.1:8000";
const OUT = new URL("../screens/", import.meta.url).pathname;

// A mid-range Android on mobile data. 360×640 is the Phase 0 baseline; the UA matters because
// AppButtons branches on it (pieces.tsx:110-117) and would otherwise render the DESKTOP app row.
const ANDROID_UA =
  "Mozilla/5.0 (Linux; Android 12; SM-A125F) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Mobile Safari/537.36";

const steps = [];
let taps = 0;

async function setState(name) {
  await fetch(`${MOCK}/__state`, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({ name }),
  });
}

async function settle(page) {
  try {
    await page.evaluate(async () => {
      const step = Math.floor(window.innerHeight * 0.8);
      for (let y = 0; y < document.body.scrollHeight; y += step) {
        window.scrollTo(0, y);
        await new Promise((r) => setTimeout(r, 60));
      }
      window.scrollTo(0, 0);
      await new Promise((r) => setTimeout(r, 120));
    });
    await page.evaluate(() => document.fonts?.ready);
  } catch {}
  await page.waitForTimeout(200);
}

async function ctxFor(browser, { locale = "fa", theme = "dark", width = 360, height = 640, ua = ANDROID_UA, cookies = true } = {}) {
  const ctx = await browser.newContext({
    viewport: { width, height },
    deviceScaleFactor: 2,
    isMobile: width <= 500,
    hasTouch: width <= 500,
    userAgent: ua,
    locale: locale === "fa" ? "fa-IR" : "en-US",
    extraHTTPHeaders: { "accept-language": locale === "fa" ? "fa-IR,fa;q=0.9" : "en-US,en;q=0.9" },
  });
  if (cookies) {
    await ctx.addCookies([
      { name: "locale", value: locale, url: SITE },
      { name: "theme", value: theme, url: SITE },
    ]);
  }
  return ctx;
}

/**
 * What a user can actually SEE without scrolling, plus what the whole page says. `foldPx` is the
 * viewport height; anything whose top is below it is below the fold on first paint.
 */
async function readScreen(page) {
  return page.evaluate(() => {
    const fold = window.innerHeight;
    const vis = (el) => {
      const s = getComputedStyle(el);
      if (s.visibility === "hidden" || s.display === "none" || parseFloat(s.opacity) < 0.05) return false;
      const r = el.getBoundingClientRect();
      return r.width > 0 && r.height > 0;
    };
    const texts = [];
    const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
    let n;
    while ((n = walker.nextNode())) {
      const s = n.nodeValue.trim();
      if (!s) continue;
      const el = n.parentElement;
      if (!el || !vis(el)) continue;
      const r = el.getBoundingClientRect();
      texts.push({ t: s, y: Math.round(r.top + window.scrollY), aboveFold: r.top + window.scrollY < fold });
    }
    const ctl = [...document.querySelectorAll("button, a[href], input, textarea, select, [role=radio], [role=button]")]
      .filter(vis)
      .map((el) => {
        const r = el.getBoundingClientRect();
        return {
          tag: el.tagName.toLowerCase(),
          cls: el.className && typeof el.className === "string" ? el.className.slice(0, 60) : "",
          label: (el.getAttribute("aria-label") || el.innerText || el.value || "").trim().replace(/\s+/g, " ").slice(0, 80),
          href: el.getAttribute("href") || null,
          disabled: !!el.disabled,
          w: Math.round(r.width),
          h: Math.round(r.height),
          y: Math.round(r.top + window.scrollY),
          aboveFold: r.top + window.scrollY < fold,
        };
      });
    return {
      fold,
      docH: document.documentElement.scrollHeight,
      scrollW: document.documentElement.scrollWidth,
      title: document.title,
      h1: [...document.querySelectorAll("h1")].map((h) => h.innerText.trim()),
      aboveFoldText: texts.filter((x) => x.aboveFold).map((x) => x.t),
      allText: texts.map((x) => x.t),
      controls: ctl,
      aboveFoldControls: ctl.filter((c) => c.aboveFold),
      // touch targets under the 44px WCAG/Android minimum, among things a finger must hit
      smallTargets: ctl.filter((c) => (c.h < 44 || c.w < 44) && c.h > 0).map((c) => ({ label: c.label, w: c.w, h: c.h, cls: c.cls })),
    };
  });
}

async function shot(page, name, note, extra = {}) {
  await settle(page);
  const file = `w-${name}.png`;
  await page.screenshot({ path: OUT + file, fullPage: true });
  const screen = await readScreen(page);
  steps.push({ file, note, taps, ...extra, screen });
  process.stdout.write(`  ${file}  (taps=${taps})  ${note}\n`);
  return screen;
}

/**
 * A tap that counts. `why` records the DECISION the user had to make to place it. A tap that CANNOT
 * land is itself a finding, so a failure is recorded and the walk continues rather than aborting —
 * an audit that stops at the first unreachable control learns nothing about what is behind it.
 */
async function tap(page, locator, why) {
  taps++;
  try {
    await locator.click({ timeout: 6000 });
    return { why, ok: true };
  } catch (e) {
    const detail = String(e).split("\n")[0].slice(0, 200);
    steps.push({ probe: "tap-failed", why, detail });
    process.stdout.write(`  !! tap failed (${why}): ${detail}\n`);
    return { why, ok: false, detail };
  }
}

/**
 * Perceptual-threshold probe: click, then poll the DOM every 16ms and record the first moment the
 * screen changed at all (100ms budget), the first moment a busy/progress affordance appeared, and
 * the moment the outcome landed. Nielsen's three thresholds, measured rather than felt.
 */
async function feedbackProbe(page, selector) {
  return page.evaluate(async (sel) => {
    const btn = document.querySelector(sel);
    if (!btn) return { error: "no button" };
    const sig = () => {
      const b = document.querySelector(sel);
      return JSON.stringify({
        text: document.body.innerText.length,
        btnText: b ? b.innerText : null,
        btnDisabled: b ? b.disabled : null,
        spinner: !!document.querySelector(".spinner"),
        widget: document.querySelector(".widget")?.innerText.slice(0, 120) ?? null,
      });
    };
    const before = sig();
    const t0 = performance.now();
    btn.click();
    let firstChange = null, firstBusy = null, settled = null;
    for (let i = 0; i < 700; i++) {
      await new Promise((r) => requestAnimationFrame(r));
      const now = performance.now() - t0;
      const s = sig();
      if (firstChange === null && s !== before) firstChange = now;
      if (firstBusy === null && (document.querySelector(".spinner") || document.querySelector("[aria-busy=true]")))
        firstBusy = now;
      if (firstChange !== null && now > 200 && settled === null) {
        // stable for 300ms → treat as settled
        const stamp = s;
        await new Promise((r) => setTimeout(r, 300));
        if (sig() === stamp) { settled = performance.now() - t0; break; }
      }
      if (now > 12000) break;
    }
    return { firstChangeMs: firstChange, firstBusyMs: firstBusy, settledMs: settled };
  }, selector);
}

// =================================================================================================

const browser = await chromium.launch({
  executablePath: "/opt/pw-browsers/chromium-1194/chrome-linux/chrome",
});
await mkdir(OUT, { recursive: true });

// ---------------------------------------------------------------------------------------------
// FLOW A — cold from Google. No cookies at all: the visitor arrives from a search result on an
// SEO landing, with whatever Accept-Language their phone sends. This is the "is it clear in five
// seconds" read, so the shot is the FIRST viewport, not the full page.
// ---------------------------------------------------------------------------------------------
console.log("FLOW A — cold from Google");
await setState("first");
{
  const ctx = await ctxFor(browser, { cookies: false });
  const page = await ctx.newPage();
  taps = 0;
  await page.goto(SITE + "/l/free-v2ray-config-germany", { waitUntil: "networkidle", timeout: 45000 });
  await settle(page);
  await page.screenshot({ path: OUT + "w-a01-cold-landing-fold.png", fullPage: false });
  const s = await readScreen(page);
  steps.push({ file: "w-a01-cold-landing-fold.png", note: "SEO landing, first viewport only, no cookies", taps, screen: s });
  console.log(`  w-a01-cold-landing-fold.png  aboveFold controls=${s.aboveFoldControls.length}`);
  await shot(page, "a02-cold-landing-full", "same landing, full page");

  // Same read on the homepage — the other cold entry.
  await page.goto(SITE + "/", { waitUntil: "networkidle", timeout: 45000 });
  await settle(page);
  await page.screenshot({ path: OUT + "w-a03-cold-home-fold.png", fullPage: false });
  const h = await readScreen(page);
  steps.push({ file: "w-a03-cold-home-fold.png", note: "homepage, first viewport only, no cookies", taps, screen: h });
  console.log(`  w-a03-cold-home-fold.png  aboveFold controls=${h.aboveFoldControls.length}`);
  await ctx.close();
}

// ---------------------------------------------------------------------------------------------
// FLOW B — first run: home → pick → claim → delivered. The tap counter runs for real here.
// ---------------------------------------------------------------------------------------------
console.log("FLOW B — first run to a delivered config");
await setState("first");
{
  const ctx = await ctxFor(browser);
  const page = await ctx.newPage();
  taps = 0;
  const nav0 = Date.now();
  await page.goto(SITE + "/", { waitUntil: "networkidle", timeout: 45000 });
  const navMs = Date.now() - nav0;
  await shot(page, "b01-home-idle", "S1 idle picker, first visit", { navMs });

  // What is the widget's default state? Is the CTA live with zero taps?
  const ctaState = await page.evaluate(() => {
    const b = document.querySelector("button.btn.cta");
    const checked = [...document.querySelectorAll("[role=radio]")].filter((r) => r.getAttribute("aria-checked") === "true");
    const grid = document.querySelector(".loc-grid");
    return {
      ctaDisabled: b ? b.disabled : null,
      ctaText: b ? b.innerText.replace(/\s+/g, " ").trim() : null,
      radios: document.querySelectorAll("[role=radio]").length,
      preChecked: checked.map((c) => c.innerText.replace(/\s+/g, " ").trim()),
      gridScrollH: grid ? grid.scrollHeight : null,
      gridClientH: grid ? grid.clientHeight : null,
      gridScrolls: grid ? grid.scrollHeight > grid.clientHeight + 2 : null,
      // does the CTA sit above the fold on arrival?
      ctaTop: b ? Math.round(b.getBoundingClientRect().top + window.scrollY) : null,
      fold: window.innerHeight,
    };
  });
  steps.push({ probe: "b-cta-on-arrival", ...ctaState });
  console.log(`  probe cta: disabled=${ctaState.ctaDisabled} preChecked=${JSON.stringify(ctaState.preChecked)} ctaTop=${ctaState.ctaTop} fold=${ctaState.fold}`);

  // A real user picks a location (even though one is pre-picked) — that is a decision + a tap.
  const cards = page.locator(".loc-card");
  const pickedName = (await cards.nth(2).innerText()).replace(/\s+/g, " ").trim();
  await tap(page, cards.nth(2), "chose a location other than the recommended default");
  await page.waitForTimeout(400);
  await shot(page, "b02-picked", `after picking the 3rd location (${pickedName})`);

  // Claim, with the perceptual-threshold probe wrapped around it.
  //
  // The mock's `claim_ok` returns a successful POST but keeps /status at has_config:false, so the
  // widget's own "the server is authoritative" effect (ClaimWidget.tsx:129-131) correctly wipes the
  // optimistic result on the reload() that follows — the card flips straight back to the picker.
  // That is the MOCK's shape, not the product's: a real claim moves the device to active_config.
  // Modelled here by intercepting /status and flipping it to the delivered shape once the claim
  // POST has been seen, which is exactly the transition the backend performs. Nothing in the app is
  // touched; the fixture is corrected, not the product.
  await setState("claim_ok");
  const LINK = "vless://8f3c1d2e-9a4b-4c7d-b1e6-2f5a8c9d0e13@de-01.gozarx-edge.net:443?type=ws&security=tls&sni=cdn.gozarx-edge.net&host=cdn.gozarx-edge.net&path=%2Fws%3Fed%3D2048&fp=chrome&alpn=h2%2Chttp%2F1.1#GozarX-FR-01";
  // The location the fixture hands back must be the one the user PICKED, or the walk would
  // photograph a country mismatch that is the harness's doing, not the product's.
  const wire = `\u{1F1EB}\u{1F1F7} ${pickedName.replace(/^.*?\s/, "")}`;
  let claimed = false;
  await page.route("**/api/public/**", async (route) => {
    const req = route.request();
    const url = req.url();
    if (url.includes("/claim") && req.method() === "POST") {
      claimed = true;
      return route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ ok: true, reason: null, location: wire, link: LINK, size: "1 GB", changed: false, retry_after: null }),
      });
    }
    if (!claimed || !url.includes("/status")) return route.continue();
    const res = await route.fetch();
    const body = await res.json();
    return route.fulfill({
      response: res,
      json: {
        ...body,
        has_config: true, status: "active_config", active: true, can_claim: false,
        usage: "0 B", usage_bytes: 0, remaining: "1 GB", configs: 1,
        cooldown: "۲۳ ساعت و ۵۸ دقیقه", location: wire, link: LINK,
      },
    });
  });
  const fb = await feedbackProbe(page, "button.btn.cta");
  taps++;
  steps.push({ probe: "b-claim-feedback", ...fb });
  console.log(`  probe claim feedback: firstChange=${fb.firstChangeMs}ms busy=${fb.firstBusyMs}ms settled=${fb.settledMs}ms`);
  await page.waitForTimeout(2000);
  await shot(page, "b03-delivered", "S3 fresh claim — the celebration card");

  // THE HAND-OFF. What does the delivered card offer, and does anything point at an install guide?
  const handoff = await page.evaluate(() => {
    const card = document.querySelector(".widget");
    const links = [...document.querySelectorAll("a[href]")].map((a) => ({
      href: a.getAttribute("href"),
      text: a.innerText.replace(/\s+/g, " ").trim().slice(0, 60),
      inCard: !!card && card.contains(a),
    }));
    const appBtns = [...document.querySelectorAll(".app-btn")].map((a) => ({
      text: a.innerText.replace(/\s+/g, " ").trim(),
      href: a.getAttribute("href").slice(0, 40),
    }));
    return {
      appButtons: appBtns,
      guideLinksInCard: links.filter((l) => l.inCard && /guide|راهنما/i.test(l.href + l.text)),
      guideLinksAnywhere: links.filter((l) => /\/guides/.test(l.href || "")),
      cardText: card ? card.innerText.replace(/\s+/g, " ").trim() : null,
      // is the config link itself visible in full, or truncated?
      codeEl: (() => {
        const c = document.querySelector(".copyfield code");
        if (!c) return null;
        return { scrollW: c.scrollWidth, clientW: c.clientWidth, truncated: c.scrollWidth > c.clientWidth + 2, text: c.innerText.slice(0, 50) };
      })(),
    };
  });
  steps.push({ probe: "b-handoff", ...handoff });
  console.log(`  probe handoff: apps=${JSON.stringify(handoff.appButtons.map(a=>a.text))} guideLinksInCard=${handoff.guideLinksInCard.length} guideLinksAnywhere=${handoff.guideLinksAnywhere.length}`);

  // Tap the copy button — is there a confirmation?
  const copyBtn = page.locator(".copyfield button").first();
  if (await copyBtn.count()) {
    await tap(page, copyBtn, "copy the config link");
    await page.waitForTimeout(300);
    await shot(page, "b04-copied", "after tapping copy — the confirmation");
  }
  await ctx.close();
}

// ---------------------------------------------------------------------------------------------
// FLOW C — the hand-off destination. If a user does find /guides, what does it cost them?
// ---------------------------------------------------------------------------------------------
console.log("FLOW C — the hand-off / guides path");
await setState("delivered");
{
  const ctx = await ctxFor(browser);
  const page = await ctx.newPage();
  taps = 0;
  await page.goto(SITE + "/", { waitUntil: "networkidle", timeout: 45000 });
  // How does a user REACH the guides from the delivered state? Enumerate every route out.
  const routesOut = await page.evaluate(() => {
    const inHeader = [...document.querySelectorAll("header a[href]")].map((a) => ({ t: a.innerText.trim(), h: a.getAttribute("href") }));
    const inFooter = [...document.querySelectorAll("footer a[href]")].map((a) => ({ t: a.innerText.trim(), h: a.getAttribute("href") }));
    const nav = document.querySelector("header nav");
    return {
      headerLinks: inHeader,
      footerLinks: inFooter,
      headerNavVisible: nav ? getComputedStyle(nav).display !== "none" : null,
      hamburger: [...document.querySelectorAll("header button")].map((b) => ({
        label: (b.getAttribute("aria-label") || b.innerText || "").trim(),
        expanded: b.getAttribute("aria-expanded"),
      })),
    };
  });
  steps.push({ probe: "c-routes-out", ...routesOut });
  console.log(`  probe routes-out: headerLinks=${routesOut.headerLinks.length} headerNavVisible=${routesOut.headerNavVisible} hamburger=${JSON.stringify(routesOut.hamburger)}`);

  // Open the menu. The header's first three buttons (fa / EN / theme) are display:none at 360px —
  // the only visible one is the burger, which is itself part of the finding.
  const burger = page.locator("header button[aria-label='menu'], header button[aria-expanded]").first();
  if (await burger.count()) {
    await tap(page, burger, "open the nav menu to look for install help");
    await page.waitForTimeout(500);
    await shot(page, "c01-menu-open", "the mobile nav menu");
    const menu = await page.evaluate(() => {
      const open = [...document.querySelectorAll("header a[href], header button")].filter((el) => {
        const r = el.getBoundingClientRect();
        return r.width > 0 && r.height > 0 && getComputedStyle(el).visibility !== "hidden";
      });
      return open.map((el) => ({
        t: (el.getAttribute("aria-label") || el.innerText).replace(/\s+/g, " ").trim().slice(0, 40),
        h: el.getAttribute("href") || null,
        h_px: Math.round(el.getBoundingClientRect().height),
      }));
    });
    steps.push({ probe: "c-menu-contents", items: menu });
    console.log(`  probe menu: ${JSON.stringify(menu)}`);
  }
  await page.goto(SITE + "/guides", { waitUntil: "networkidle", timeout: 45000 });
  taps++;
  await shot(page, "c02-guides-index", "guides index");
  await page.goto(SITE + "/guides/android", { waitUntil: "networkidle", timeout: 45000 });
  taps++;
  const g = await shot(page, "c03-guide-android", "android guide — the hand-off destination");

  // Does the guide know the user already has a link? Does it hand it back to them?
  const guideProbe = await page.evaluate(() => {
    const txt = document.body.innerText;
    return {
      mentionsConfigLink: /vless:\/\//.test(txt),
      hasCopyField: !!document.querySelector(".copyfield"),
      hasWidget: !!document.querySelector(".widget"),
      linksBackToHome: [...document.querySelectorAll("a[href]")].filter((a) => a.getAttribute("href") === "/").length,
      stepCount: document.querySelectorAll(".tstep").length,
      downloadLinks: [...document.querySelectorAll("a[href^='http']")].map((a) => a.getAttribute("href")),
      troubleCount: document.querySelectorAll("details").length,
    };
  });
  steps.push({ probe: "c-guide-android", ...guideProbe });
  console.log(`  probe guide: steps=${guideProbe.stepCount} mentionsLink=${guideProbe.mentionsConfigLink} hasCopyField=${guideProbe.hasCopyField} dl=${JSON.stringify(guideProbe.downloadLinks)}`);
  await ctx.close();
}

// ---------------------------------------------------------------------------------------------
// FLOW D — change location from a delivered config.
// ---------------------------------------------------------------------------------------------
console.log("FLOW D — change location");
await setState("delivered");
{
  const ctx = await ctxFor(browser);
  const page = await ctx.newPage();
  taps = 0;
  await page.goto(SITE + "/", { waitUntil: "networkidle", timeout: 45000 });
  await shot(page, "d01-delivered-returning", "S4 returning user with a live config");
  const chg = page.locator(".chg-btn").first();
  if (await chg.count()) {
    await tap(page, chg, "open the change-location picker");
    await page.waitForTimeout(500);
    await shot(page, "d02-change-picker", "change-location picker expanded");
  }
  await ctx.close();
}

// ---------------------------------------------------------------------------------------------
// FLOW E — invite friends / more volume, and F — status page (usage).
// ---------------------------------------------------------------------------------------------
console.log("FLOW E/F — invite + status");
await setState("delivered");
{
  const ctx = await ctxFor(browser);
  const page = await ctx.newPage();
  taps = 0;
  await page.goto(SITE + "/status", { waitUntil: "networkidle", timeout: 45000 });
  const st = await shot(page, "e01-status", "status page — usage, invites, history");
  const statusProbe = await page.evaluate(() => {
    const tabs = [...document.querySelectorAll("[role=tab], .tabbtn, .seg-btn, nav button")].map((b) => b.innerText.trim());
    return {
      tabs,
      hasRefLink: !!document.body.innerText.match(/ref=/),
      copyFields: document.querySelectorAll(".copyfield").length,
      h1: [...document.querySelectorAll("h1")].map((h) => h.innerText.trim()),
      title: document.title,
    };
  });
  steps.push({ probe: "f-status", ...statusProbe });
  console.log(`  probe status: title="${statusProbe.title}" h1=${JSON.stringify(statusProbe.h1)} tabs=${JSON.stringify(statusProbe.tabs)}`);

  // Walk the status page's own sub-navigation, whatever it turns out to be.
  const segs = page.locator("[role=tab], .seg-btn, .tabbtn");
  const n = await segs.count();
  for (let i = 0; i < Math.min(n, 4); i++) {
    await tap(page, segs.nth(i), `status sub-tab ${i}`);
    await page.waitForTimeout(400);
    await shot(page, `e0${i + 2}-status-tab${i}`, `status sub-tab ${i}`);
  }
  await ctx.close();
}

// ---------------------------------------------------------------------------------------------
// FLOW G — language switch. Where is it, what does it cost, and does it survive a navigation?
// ---------------------------------------------------------------------------------------------
console.log("FLOW G — language switch");
await setState("first");
{
  const ctx = await ctxFor(browser);
  const page = await ctx.newPage();
  taps = 0;
  await page.goto(SITE + "/", { waitUntil: "networkidle", timeout: 45000 });
  const langProbe = await page.evaluate(() => {
    const cands = [...document.querySelectorAll("button, a")].filter((el) =>
      /EN|FA|فارسی|English|زبان|lang/i.test((el.getAttribute("aria-label") || "") + el.innerText),
    );
    return cands.map((el) => {
      const r = el.getBoundingClientRect();
      return {
        tag: el.tagName.toLowerCase(),
        label: (el.getAttribute("aria-label") || el.innerText).replace(/\s+/g, " ").trim().slice(0, 40),
        w: Math.round(r.width), h: Math.round(r.height),
        y: Math.round(r.top + window.scrollY),
        inHeader: !!el.closest("header"), inFooter: !!el.closest("footer"),
        aboveFold: r.top + window.scrollY < window.innerHeight,
      };
    });
  });
  steps.push({ probe: "g-lang-controls", controls: langProbe });
  console.log(`  probe lang: ${JSON.stringify(langProbe)}`);

  // How many taps does a language change cost at 360px? Count them honestly: if the control is
  // hidden behind the burger, opening the burger is a tap and finding it there is a decision.
  const enDirect = page.locator("header button", { hasText: /^EN$/ }).first();
  const directVisible = (await enDirect.count()) ? await enDirect.isVisible() : false;
  steps.push({ probe: "g-direct-visible", directVisible });
  if (!directVisible) {
    const burger = page.locator("header button[aria-label='menu'], header button[aria-expanded]").first();
    if (await burger.count()) await tap(page, burger, "open the burger to reach the language control");
    await page.waitForTimeout(500);
    await shot(page, "g01-menu-for-lang", "the menu, looking for the language control");
  }
  const enAny = page.locator("button", { hasText: /^EN$/ }).first();
  if ((await enAny.count()) && (await enAny.isVisible())) {
    await tap(page, enAny, "switch to English");
    await page.waitForTimeout(1500);
    await shot(page, "g02-after-lang", "after switching language");
    const after = await page.evaluate(() => ({
      dir: document.documentElement.dir,
      lang: document.documentElement.lang,
      h1: [...document.querySelectorAll("h1")].map((h) => h.innerText.trim()),
      url: location.pathname + location.search,
    }));
    steps.push({ probe: "g-after-lang", ...after });
    console.log(`  probe after-lang: ${JSON.stringify(after)}`);
    // does it survive a navigation?
    await page.goto(SITE + "/faq", { waitUntil: "networkidle", timeout: 30000 });
    const persisted = await page.evaluate(() => ({ dir: document.documentElement.dir, lang: document.documentElement.lang }));
    steps.push({ probe: "g-lang-persist", ...persisted });
    console.log(`  probe lang persist: ${JSON.stringify(persisted)}`);
  } else {
    await shot(page, "g02-no-lang-control", "no reachable language control at 360px");
  }
  await ctx.close();
}

// ---------------------------------------------------------------------------------------------
// FLOW H — the error / limit states, each read as "what do I do now".
// ---------------------------------------------------------------------------------------------
console.log("FLOW H — limits and errors");
for (const [state, slug, note] of [
  ["cooldown", "h01-cooldown", "already claimed today"],
  ["exhausted", "h02-exhausted", "daily volume spent"],
  ["panel_error", "h03-panel-error", "backend down"],
  ["no_locations", "h04-no-locations", "squad serves nothing"],
]) {
  await setState(state);
  const ctx = await ctxFor(browser);
  const page = await ctx.newPage();
  taps = 0;
  await page.goto(SITE + "/", { waitUntil: state === "panel_error" ? "domcontentloaded" : "networkidle", timeout: 30000 }).catch(() => {});
  await page.waitForTimeout(state === "panel_error" ? 2500 : 800);
  const s = await shot(page, slug, note);
  // What are the ways OUT of this screen?
  const outs = await page.evaluate(() => {
    const w = document.querySelector(".widget");
    if (!w) return { widget: null };
    return {
      widgetText: w.innerText.replace(/\s+/g, " ").trim(),
      widgetControls: [...w.querySelectorAll("button, a[href]")].map((b) => ({
        t: b.innerText.replace(/\s+/g, " ").trim(), h: b.getAttribute("href") || null,
      })),
    };
  });
  steps.push({ probe: `h-${state}`, ...outs });
  console.log(`  probe ${state}: controls=${JSON.stringify(outs.widgetControls)}`);
  await ctx.close();
}

// rate_limited needs a click to surface
console.log("FLOW H — rate limited (needs a claim attempt)");
await setState("rate_limited");
{
  const ctx = await ctxFor(browser);
  const page = await ctx.newPage();
  taps = 0;
  await page.goto(SITE + "/", { waitUntil: "networkidle", timeout: 30000 });
  await page.locator("button.btn.cta").first().click({ timeout: 8000 }).catch(() => {});
  taps++;
  await page.waitForTimeout(1500);
  await shot(page, "h05-rate-limited", "after a claim that hit the 429 guard");
  const outs = await page.evaluate(() => {
    const w = document.querySelector(".widget");
    return w ? { widgetText: w.innerText.replace(/\s+/g, " ").trim() } : {};
  });
  steps.push({ probe: "h-rate_limited", ...outs });
  console.log(`  probe rate_limited: "${(outs.widgetText || "").slice(0, 120)}"`);
  await ctx.close();
}

console.log("FLOW H — location unavailable (needs a claim attempt)");
await setState("location_unavailable");
{
  const ctx = await ctxFor(browser);
  const page = await ctx.newPage();
  taps = 0;
  await page.goto(SITE + "/", { waitUntil: "networkidle", timeout: 30000 });
  await page.locator("button.btn.cta").first().click({ timeout: 8000 }).catch(() => {});
  taps++;
  await page.waitForTimeout(1500);
  await shot(page, "h06-location-unavailable", "after claiming a location the squad dropped");
  const outs = await page.evaluate(() => {
    const w = document.querySelector(".widget");
    return w ? { widgetText: w.innerText.replace(/\s+/g, " ").trim() } : {};
  });
  steps.push({ probe: "h-location_unavailable", ...outs });
  console.log(`  probe location_unavailable: "${(outs.widgetText || "").slice(0, 160)}"`);
  await ctx.close();
}

// ---------------------------------------------------------------------------------------------
// FLOW I — the slow network read. 400kbps / 400ms is an ordinary filtered Iranian mobile link.
// What is on screen at 1s, 3s, 10s?
// ---------------------------------------------------------------------------------------------
console.log("FLOW I — slow network timeline");
await setState("slow");
{
  const ctx = await ctxFor(browser);
  const page = await ctx.newPage();
  const cdp = await ctx.newCDPSession(page);
  await cdp.send("Network.enable");
  await cdp.send("Network.emulateNetworkConditions", {
    offline: false, latency: 400, downloadThroughput: (400 * 1024) / 8, uploadThroughput: (400 * 1024) / 8,
  });
  taps = 0;
  const t0 = Date.now();
  page.goto(SITE + "/", { waitUntil: "domcontentloaded", timeout: 60000 }).catch(() => {});
  for (const ms of [1000, 3000, 10000]) {
    while (Date.now() - t0 < ms) await page.waitForTimeout(100);
    const file = `w-i0${ms / 1000 === 10 ? 3 : ms / 1000 === 3 ? 2 : 1}-slow-${ms}ms.png`;
    await page.screenshot({ path: OUT + file, fullPage: false }).catch(() => {});
    const st = await page.evaluate(() => ({
      hasSkeleton: !!document.querySelector(".skeleton"),
      hasWidget: !!document.querySelector(".widget"),
      widgetText: document.querySelector(".widget")?.innerText.replace(/\s+/g, " ").trim().slice(0, 100) ?? null,
      bodyLen: document.body ? document.body.innerText.length : 0,
    })).catch(() => ({}));
    steps.push({ file, note: `slow network at ${ms}ms`, atMs: ms, ...st });
    console.log(`  ${file}  skeleton=${st.hasSkeleton} bodyLen=${st.bodyLen}`);
  }
  await ctx.close();
}

// ---------------------------------------------------------------------------------------------
// FLOW J — the returning user. Same device, cookie already set, config already live. How much of
// the first-run journey do they repeat?
// ---------------------------------------------------------------------------------------------
console.log("FLOW J — returning user");
await setState("delivered");
{
  const ctx = await ctxFor(browser);
  const page = await ctx.newPage();
  taps = 0;
  await page.goto(SITE + "/", { waitUntil: "networkidle", timeout: 45000 });
  await settle(page);
  await page.screenshot({ path: OUT + "w-j01-returning-fold.png", fullPage: false });
  const r = await readScreen(page);
  steps.push({ file: "w-j01-returning-fold.png", note: "returning user, first viewport", taps, screen: r });
  const ret = await page.evaluate(() => {
    const w = document.querySelector(".widget");
    const code = document.querySelector(".copyfield code");
    return {
      widgetTop: w ? Math.round(w.getBoundingClientRect().top + window.scrollY) : null,
      linkTop: code ? Math.round(code.getBoundingClientRect().top + window.scrollY) : null,
      fold: window.innerHeight,
      linkAboveFold: code ? code.getBoundingClientRect().top + window.scrollY < window.innerHeight : null,
      appBtnTop: (() => { const a = document.querySelector(".app-btn"); return a ? Math.round(a.getBoundingClientRect().top + window.scrollY) : null; })(),
    };
  });
  steps.push({ probe: "j-returning", ...ret });
  console.log(`  probe returning: widgetTop=${ret.widgetTop} linkTop=${ret.linkTop} fold=${ret.fold} linkAboveFold=${ret.linkAboveFold} appBtnTop=${ret.appBtnTop}`);
  await ctx.close();
}

// ---------------------------------------------------------------------------------------------
// FLOW K — the English side of the same first run, since half the trust copy is bilingual.
// ---------------------------------------------------------------------------------------------
console.log("FLOW K — English first run");
await setState("first");
{
  const ctx = await ctxFor(browser, { locale: "en" });
  const page = await ctx.newPage();
  taps = 0;
  await page.goto(SITE + "/", { waitUntil: "networkidle", timeout: 45000 });
  await shot(page, "k01-home-en", "English homepage, first visit");
  await ctx.close();
}

await browser.close();
await setState("first");
await writeFile(new URL("../walk.json", import.meta.url).pathname, JSON.stringify({ steps }, null, 2));
console.log(`\nwalk -> audit/walk.json  (${steps.filter((s) => s.file).length} shots)`);
