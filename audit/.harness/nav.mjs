// Phase 1 — navigation, language and tap-cost probes. READ-ONLY.
// The earlier sheet capture was taken on a 1600px-tall viewport and cropped to its top 640px; the
// sheet is a BOTTOM sheet, so it fell outside the crop. Everything here runs at a real 360×640.

import { chromium } from "playwright";
import { mkdir, writeFile } from "node:fs/promises";

const SITE = "http://127.0.0.1:3100";
const MOCK = "http://127.0.0.1:8000";
const OUT = new URL("../screens/", import.meta.url).pathname;
const ANDROID_UA =
  "Mozilla/5.0 (Linux; Android 12; SM-A125F) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Mobile Safari/537.36";

const probes = [];
const setState = (n) =>
  fetch(`${MOCK}/__state`, { method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify({ name: n }) });

async function phone(browser, locale = "fa", theme = "dark", w = 360, h = 640) {
  const ctx = await browser.newContext({
    viewport: { width: w, height: h }, deviceScaleFactor: 2, isMobile: true, hasTouch: true,
    userAgent: ANDROID_UA, locale: locale === "fa" ? "fa-IR" : "en-US",
    extraHTTPHeaders: { "accept-language": locale === "fa" ? "fa-IR,fa;q=0.9" : "en-US,en;q=0.9" },
  });
  await ctx.addCookies([
    { name: "locale", value: locale, url: SITE },
    { name: "theme", value: theme, url: SITE },
  ]);
  return ctx;
}

const browser = await chromium.launch({ executablePath: "/opt/pw-browsers/chromium-1194/chrome-linux/chrome" });
await mkdir(OUT, { recursive: true });

// --- 1. the mobile sheet, at real phone height -------------------------------------------------
{
  await setState("delivered");
  const ctx = await phone(browser);
  const page = await ctx.newPage();
  await page.goto(SITE + "/", { waitUntil: "networkidle", timeout: 45000 });
  await page.locator("button.burger").click({ timeout: 6000 });
  await page.waitForTimeout(700);
  await page.screenshot({ path: OUT + "w-nav-sheet-open.png" });
  const sheet = await page.evaluate(() => {
    const s = document.querySelector(".sheet");
    if (!s) return null;
    const r = s.getBoundingClientRect();
    const cs = getComputedStyle(s);
    return {
      top: Math.round(r.top), bottom: Math.round(r.bottom), h: Math.round(r.height),
      transform: cs.transform, position: cs.position,
      viewportH: window.innerHeight,
      insideViewport: r.top < window.innerHeight && r.bottom > 0,
      links: [...s.querySelectorAll("a[href]")].map((a) => ({
        t: a.innerText.trim(), h: a.getAttribute("href"),
        px: Math.round(a.getBoundingClientRect().height),
        visible: a.getBoundingClientRect().top < window.innerHeight,
      })),
      buttons: [...s.querySelectorAll("button")].map((b) => ({
        t: (b.innerText || b.getAttribute("aria-label") || "").trim(),
        px: Math.round(b.getBoundingClientRect().height),
        w: Math.round(b.getBoundingClientRect().width),
        visible: b.getBoundingClientRect().top < window.innerHeight,
      })),
    };
  });
  probes.push({ what: "mobile-sheet", ...sheet });
  console.log(`  sheet: top=${sheet.top} h=${sheet.h} viewportH=${sheet.viewportH} inside=${sheet.insideViewport}`);
  console.log(`  sheet links: ${JSON.stringify(sheet.links)}`);
  console.log(`  sheet buttons: ${JSON.stringify(sheet.buttons)}`);
  await ctx.close();
}

// --- 2. the true cost of a language switch -----------------------------------------------------
{
  await setState("first");
  const ctx = await phone(browser);
  const page = await ctx.newPage();
  await page.goto(SITE + "/", { waitUntil: "networkidle", timeout: 45000 });
  let taps = 0;
  await page.locator("button.burger").click({ timeout: 6000 }); taps++;
  await page.waitForTimeout(600);
  const en = page.locator(".sheet button", { hasText: /^English$/ }).first();
  const reachable = (await en.count()) > 0 && (await en.isVisible());
  if (reachable) {
    await en.click({ timeout: 6000 }); taps++;
    await page.waitForTimeout(2000);
    await page.screenshot({ path: OUT + "w-nav-after-lang-en.png" });
  }
  const after = await page.evaluate(() => ({
    dir: document.documentElement.dir, lang: document.documentElement.lang,
    h1: [...document.querySelectorAll("h1")].map((h) => h.innerText.trim()),
    url: location.pathname,
  }));
  probes.push({ what: "lang-switch", taps, reachable, ...after });
  console.log(`  lang switch: taps=${taps} reachable=${reachable} -> ${JSON.stringify(after)}`);

  // does it persist across a navigation?
  await page.goto(SITE + "/faq", { waitUntil: "networkidle", timeout: 30000 });
  const persist = await page.evaluate(() => ({ dir: document.documentElement.dir, lang: document.documentElement.lang }));
  probes.push({ what: "lang-persist", ...persist });
  console.log(`  lang persist on /faq: ${JSON.stringify(persist)}`);
  await ctx.close();
}

// --- 3. the whole primary journey, counted honestly --------------------------------------------
// Screens = distinct rendered views. Decisions = points where the user must choose between
// alternatives. Fields = anything requiring typed input.
{
  await setState("first");
  const ctx = await phone(browser);
  const page = await ctx.newPage();
  const journey = [];
  let taps = 0, screens = 0, decisions = 0, fields = 0, scrolls = 0;

  await page.goto(SITE + "/", { waitUntil: "networkidle", timeout: 45000 });
  screens++;
  const arrival = await page.evaluate(() => {
    const cta = document.querySelector("button.btn.cta");
    return {
      ctaY: cta ? Math.round(cta.getBoundingClientRect().top + window.scrollY) : null,
      fold: window.innerHeight,
      ctaEnabled: cta ? !cta.disabled : null,
      preselected: [...document.querySelectorAll("[role=radio][aria-checked=true]")].map((r) => r.innerText.replace(/\s+/g, " ").trim()),
    };
  });
  journey.push({ step: "arrive at /", ...arrival });
  // reaching the CTA at all costs a scroll on a 640px screen
  if (arrival.ctaY > arrival.fold) { scrolls++; journey.push({ step: "scroll to reach the CTA", px: arrival.ctaY - arrival.fold }); }
  decisions++; journey.push({ step: "decide which location", note: "12 offered, 6 visible without scrolling the inner grid" });
  await page.locator(".loc-card").nth(2).click(); taps++;
  await page.waitForTimeout(300);

  // the claim
  await page.route("**/api/public/**", async (route) => {
    const req = route.request();
    if (req.url().includes("/claim") && req.method() === "POST") {
      return route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({ ok: true, location: "\u{1F1EB}\u{1F1F7} France", link: "vless://x@fr-01.example.net:443?type=ws#GozarX-FR", changed: false }) });
    }
    if (req.url().includes("/status")) {
      const res = await route.fetch();
      const b = await res.json();
      return route.fulfill({ response: res, json: { ...b, has_config: true, active: true, status: "active_config", can_claim: false, location: "\u{1F1EB}\u{1F1F7} France", link: "vless://x@fr-01.example.net:443?type=ws#GozarX-FR", remaining: "23h 58m", usage: "0 B", usage_bytes: 0, configs: 1 } });
    }
    return route.continue();
  });
  await page.locator("button.btn.cta").click(); taps++;
  await page.waitForTimeout(2500);
  screens++;
  journey.push({ step: "claim resolves → config card", screens });

  const card = await page.evaluate(() => {
    const w = document.querySelector(".widget");
    return {
      hasLink: !!w?.querySelector(".copyfield code"),
      appButtons: [...(w?.querySelectorAll(".app-btn") ?? [])].map((a) => a.innerText.replace(/\s+/g, " ").trim()),
      // does anything here tell a user WITHOUT the app what to do?
      installHints: [...(w?.querySelectorAll("a[href]") ?? [])].map((a) => a.getAttribute("href")).filter((h) => /guides|play\.google|apps\.apple|github/.test(h || "")),
      cardCopy: w ? w.innerText.replace(/\s+/g, " ").trim() : null,
    };
  });
  journey.push({ step: "the hand-off card", ...card });
  decisions++; journey.push({ step: "decide which app to tap", note: `${card.appButtons.length} app buttons, no install path for a user who has neither` });

  probes.push({ what: "primary-journey", taps, screens, decisions, fields, scrolls, journey });
  console.log(`\n  PRIMARY JOURNEY: taps=${taps} screens=${screens} decisions=${decisions} fields=${fields} scrolls=${scrolls}`);
  console.log(`  app buttons: ${JSON.stringify(card.appButtons)}  installHints=${JSON.stringify(card.installHints)}`);
  await ctx.close();
}

// --- 4. what a returning user repeats -----------------------------------------------------------
{
  await setState("delivered");
  const ctx = await phone(browser);
  const page = await ctx.newPage();
  await page.goto(SITE + "/", { waitUntil: "networkidle", timeout: 45000 });
  await page.screenshot({ path: OUT + "w-nav-returning-fold.png" });
  const r = await page.evaluate(() => {
    const code = document.querySelector(".copyfield code");
    const copyBtn = document.querySelector(".copyfield button");
    const app = document.querySelector(".app-btn");
    const f = window.innerHeight;
    return {
      fold: f,
      linkY: code ? Math.round(code.getBoundingClientRect().top + window.scrollY) : null,
      copyBtnY: copyBtn ? Math.round(copyBtn.getBoundingClientRect().top + window.scrollY) : null,
      copyBtnVisible: copyBtn ? copyBtn.getBoundingClientRect().top < f : null,
      appY: app ? Math.round(app.getBoundingClientRect().top + window.scrollY) : null,
      appVisible: app ? app.getBoundingClientRect().top < f : null,
    };
  });
  probes.push({ what: "returning-user", ...r });
  console.log(`\n  RETURNING: fold=${r.fold} copyBtnY=${r.copyBtnY} (visible=${r.copyBtnVisible}) appY=${r.appY} (visible=${r.appVisible})`);
  await ctx.close();
}

// --- 5. touch-target census on the primary path -------------------------------------------------
{
  await setState("first");
  const ctx = await phone(browser);
  const page = await ctx.newPage();
  for (const [route, slug] of [["/", "home"], ["/status", "status"], ["/guides/android", "guide"]]) {
    if (route === "/status") await setState("delivered");
    await page.goto(SITE + route, { waitUntil: "networkidle", timeout: 45000 });
    await page.waitForTimeout(600);
    const small = await page.evaluate(() =>
      [...document.querySelectorAll("button, a[href], input, [role=radio]")]
        .filter((el) => { const r = el.getBoundingClientRect(); return r.width > 0 && r.height > 0; })
        .map((el) => { const r = el.getBoundingClientRect(); return { t: (el.getAttribute("aria-label") || el.innerText).replace(/\s+/g, " ").trim().slice(0, 32), w: Math.round(r.width), h: Math.round(r.height) }; })
        .filter((x) => x.h < 44 || x.w < 44),
    );
    probes.push({ what: "small-targets", route: slug, count: small.length, items: small });
    console.log(`  ${slug}: ${small.length} controls under 44px — ${JSON.stringify(small.slice(0, 8))}`);
  }
  await ctx.close();
}

await browser.close();
await setState("first");
await writeFile(new URL("../nav.json", import.meta.url).pathname, JSON.stringify({ probes }, null, 2));
console.log("\nnav -> audit/nav.json");
