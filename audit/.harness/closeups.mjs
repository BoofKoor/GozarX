// Phase 1 close-ups — READ-ONLY. Full-page shots of a 14,000px document render the claim card at
// ~7% scale, which is unreadable and therefore unciteable. These crop the widget (and the other
// decision points) to their own bounding box so a finding can point at something legible.

import { chromium } from "playwright";
import { mkdir, writeFile } from "node:fs/promises";

const SITE = "http://127.0.0.1:3100";
const MOCK = "http://127.0.0.1:8000";
const OUT = new URL("../screens/", import.meta.url).pathname;
const ANDROID_UA =
  "Mozilla/5.0 (Linux; Android 12; SM-A125F) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Mobile Safari/537.36";

const probes = [];

const setState = (name) =>
  fetch(`${MOCK}/__state`, { method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify({ name }) });

async function ctxFor(browser, { locale = "fa", theme = "dark", width = 360, height = 640 } = {}) {
  const ctx = await browser.newContext({
    viewport: { width, height }, deviceScaleFactor: 2, isMobile: true, hasTouch: true,
    userAgent: ANDROID_UA, locale: locale === "fa" ? "fa-IR" : "en-US",
    extraHTTPHeaders: { "accept-language": locale === "fa" ? "fa-IR,fa;q=0.9" : "en-US,en;q=0.9" },
  });
  await ctx.addCookies([
    { name: "locale", value: locale, url: SITE },
    { name: "theme", value: theme, url: SITE },
  ]);
  return ctx;
}

async function settle(page) {
  try {
    await page.evaluate(async () => {
      const step = Math.floor(window.innerHeight * 0.8);
      for (let y = 0; y < document.body.scrollHeight; y += step) {
        window.scrollTo(0, y);
        await new Promise((r) => setTimeout(r, 50));
      }
      window.scrollTo(0, 0);
      await new Promise((r) => setTimeout(r, 100));
    });
    await page.evaluate(() => document.fonts?.ready);
  } catch {}
  await page.waitForTimeout(200);
}

/** Crop to one element's box. Falls back to a viewport shot when the selector is absent. */
async function crop(page, sel, file, pad = 8) {
  const el = page.locator(sel).first();
  if (!(await el.count())) {
    await page.screenshot({ path: OUT + file });
    return { file, note: "selector missing — viewport shot" };
  }
  const box = await el.boundingBox();
  if (!box) { await page.screenshot({ path: OUT + file }); return { file, note: "no box" }; }
  await page.screenshot({
    path: OUT + file,
    clip: {
      x: Math.max(0, box.x - pad), y: Math.max(0, box.y - pad),
      width: Math.min(box.width + pad * 2, 360 - Math.max(0, box.x - pad)),
      height: box.height + pad * 2,
    },
  });
  return { file, box: { w: Math.round(box.width), h: Math.round(box.height) } };
}

const browser = await chromium.launch({ executablePath: "/opt/pw-browsers/chromium-1194/chrome-linux/chrome" });
await mkdir(OUT, { recursive: true });

// --- the delivered config card, both locales, at readable scale -------------------------------
for (const locale of ["fa", "en"]) {
  await setState("delivered");
  const ctx = await ctxFor(browser, { locale });
  const page = await ctx.newPage();
  await page.goto(SITE + "/", { waitUntil: "networkidle", timeout: 45000 });
  await settle(page);
  const r = await crop(page, ".widget", `w-cu-config-card-${locale}.png`);
  probes.push({ ...r, locale, what: "delivered config card" });
  console.log(`  w-cu-config-card-${locale}.png ${JSON.stringify(r.box)}`);

  // Every label inside the card, in DOM order — the copy audit's raw material.
  const labels = await page.evaluate(() => {
    const w = document.querySelector(".widget");
    if (!w) return null;
    const out = [];
    const walk = document.createTreeWalker(w, NodeFilter.SHOW_TEXT);
    let n;
    while ((n = walk.nextNode())) { const s = n.nodeValue.trim(); if (s) out.push(s); }
    return out;
  });
  probes.push({ what: "config-card-labels", locale, labels });
  await ctx.close();
}

// --- the idle picker + CTA, cropped, and the fold line measured -------------------------------
{
  await setState("first");
  const ctx = await ctxFor(browser);
  const page = await ctx.newPage();
  await page.goto(SITE + "/", { waitUntil: "networkidle", timeout: 45000 });
  await settle(page);
  probes.push({ ...(await crop(page, ".widget", "w-cu-picker-fa.png")), what: "idle picker" });

  // Where does each decision point sit relative to a 640px fold?
  const geom = await page.evaluate(() => {
    const y = (s) => { const e = document.querySelector(s); return e ? Math.round(e.getBoundingClientRect().top + window.scrollY) : null; };
    const h = (s) => { const e = document.querySelector(s); return e ? Math.round(e.getBoundingClientRect().height) : null; };
    const grid = document.querySelector(".loc-grid");
    const trust = document.querySelector(".trust-row");
    return {
      fold: window.innerHeight,
      heroH1: y("h1"), widget: y(".widget"), pickLabel: y(".pick-label"),
      firstCard: y(".loc-card"), cta: y("button.btn.cta"), reassure: y(".reassure"),
      widgetH: h(".widget"), gridH: h(".loc-grid"),
      gridScrollH: grid ? grid.scrollHeight : null,
      gridOverflows: grid ? grid.scrollHeight > grid.clientHeight + 2 : null,
      cardsVisibleInGrid: grid ? [...grid.querySelectorAll(".loc-card")].filter((c) => {
        const cr = c.getBoundingClientRect(), gr = grid.getBoundingClientRect();
        return cr.top >= gr.top - 2 && cr.bottom <= gr.bottom + 2;
      }).length : null,
      cardsTotal: document.querySelectorAll(".loc-card").length,
      // the hero trust pills: do they overflow their row?
      trustScrollW: trust ? trust.scrollWidth : null,
      trustClientW: trust ? trust.clientWidth : null,
      trustOverflows: trust ? trust.scrollWidth > trust.clientWidth + 2 : null,
      trustOverflowX: trust ? getComputedStyle(trust).overflowX : null,
      trustPills: trust ? [...trust.children].map((p) => ({
        t: p.innerText.replace(/\s+/g, " ").trim(),
        fullyVisible: (() => { const pr = p.getBoundingClientRect(), tr = trust.getBoundingClientRect(); return pr.left >= tr.left - 1 && pr.right <= tr.right + 1; })(),
      })) : null,
    };
  });
  probes.push({ what: "home-geometry", ...geom });
  console.log(`  geometry: ${JSON.stringify(geom, null, 1)}`);
  probes.push({ ...(await crop(page, ".trust-row", "w-cu-trust-row.png")), what: "hero trust pills" });
  await ctx.close();
}

// --- each error / limit state, cropped to the widget ------------------------------------------
for (const [state, slug] of [["cooldown", "cooldown"], ["exhausted", "exhausted"], ["panel_error", "panel-error"], ["no_locations", "no-locations"]]) {
  await setState(state);
  const ctx = await ctxFor(browser);
  const page = await ctx.newPage();
  await page.goto(SITE + "/", { waitUntil: state === "panel_error" ? "domcontentloaded" : "networkidle", timeout: 30000 }).catch(() => {});
  await page.waitForTimeout(state === "panel_error" ? 2500 : 900);
  probes.push({ ...(await crop(page, ".widget", `w-cu-${slug}.png`)), what: state });
  console.log(`  w-cu-${slug}.png`);
  await ctx.close();
}

// --- the two claim-time errors, which need a tap ----------------------------------------------
for (const [state, slug] of [["rate_limited", "rate-limited"], ["location_unavailable", "location-unavailable"]]) {
  await setState(state);
  const ctx = await ctxFor(browser);
  const page = await ctx.newPage();
  await page.goto(SITE + "/", { waitUntil: "networkidle", timeout: 30000 });
  await page.locator("button.btn.cta").first().click({ timeout: 8000 }).catch(() => {});
  await page.waitForTimeout(1500);
  probes.push({ ...(await crop(page, ".widget", `w-cu-${slug}.png`)), what: state });
  console.log(`  w-cu-${slug}.png`);
  await ctx.close();
}

// --- the header / menu, open --------------------------------------------------------------------
{
  await setState("delivered");
  const ctx = await ctxFor(browser);
  const page = await ctx.newPage();
  await page.goto(SITE + "/", { waitUntil: "networkidle", timeout: 45000 });
  await page.locator("header button[aria-expanded]").first().click({ timeout: 6000 }).catch(() => {});
  await page.waitForTimeout(500);
  await page.screenshot({ path: OUT + "w-cu-menu-open.png" });
  const nav = await page.evaluate(() => {
    const header = document.querySelector("header");
    const all = [...header.querySelectorAll("a[href], button")].map((el) => {
      const r = el.getBoundingClientRect();
      const cs = getComputedStyle(el);
      return {
        t: (el.getAttribute("aria-label") || el.innerText).replace(/\s+/g, " ").trim().slice(0, 30),
        href: el.getAttribute("href") || null,
        display: cs.display, vis: cs.visibility,
        w: Math.round(r.width), h: Math.round(r.height),
        rendered: r.width > 0 && r.height > 0,
      };
    });
    // and the drawer, wherever it lives
    const drawer = document.querySelector("[class*=drawer], [class*=sheet], nav");
    return {
      headerControls: all,
      drawerHTML: drawer ? drawer.className : null,
      drawerLinks: drawer ? [...drawer.querySelectorAll("a[href]")].map((a) => ({ t: a.innerText.trim(), h: a.getAttribute("href") })) : null,
    };
  });
  probes.push({ what: "header-nav", ...nav });
  console.log(`  header: ${JSON.stringify(nav.headerControls)}`);
  console.log(`  drawer: ${JSON.stringify(nav.drawerLinks)}`);
  await ctx.close();
}

// --- the footer, where the language control actually lives -------------------------------------
{
  await setState("first");
  const ctx = await ctxFor(browser);
  const page = await ctx.newPage();
  await page.goto(SITE + "/", { waitUntil: "networkidle", timeout: 45000 });
  await settle(page);
  const fy = await page.evaluate(() => {
    const btn = [...document.querySelectorAll("footer button")].find((b) => /English|فارسی/.test(b.innerText));
    if (!btn) return null;
    btn.scrollIntoView({ block: "center" });
    return { docH: document.documentElement.scrollHeight, y: Math.round(btn.getBoundingClientRect().top + window.scrollY) };
  });
  await page.waitForTimeout(300);
  probes.push({ ...(await crop(page, "footer", "w-cu-footer.png")), what: "footer (language + theme controls)", ...fy });
  console.log(`  footer lang control at y=${fy?.y} of docH=${fy?.docH}`);
  await ctx.close();
}

// --- the android guide, cropped to its steps ----------------------------------------------------
{
  const ctx = await ctxFor(browser);
  const page = await ctx.newPage();
  await page.goto(SITE + "/guides/android", { waitUntil: "networkidle", timeout: 45000 });
  await settle(page);
  probes.push({ ...(await crop(page, ".tl", "w-cu-guide-android-steps.png")), what: "android guide steps" });
  const txt = await page.evaluate(() => ({
    steps: [...document.querySelectorAll(".tstep")].map((s) => s.innerText.replace(/\s+/g, " ").trim()),
    trouble: [...document.querySelectorAll("details")].map((d) => d.innerText.replace(/\s+/g, " ").trim()),
  }));
  probes.push({ what: "guide-android-copy", ...txt });
  console.log(`  guide steps:\n${txt.steps.map((s, i) => `    ${i + 1}. ${s}`).join("\n")}`);
  await ctx.close();
}

// --- the status page, cropped section by section -------------------------------------------------
{
  await setState("delivered");
  const ctx = await ctxFor(browser);
  const page = await ctx.newPage();
  await page.goto(SITE + "/status", { waitUntil: "networkidle", timeout: 45000 });
  await settle(page);
  await page.screenshot({ path: OUT + "w-cu-status-fold.png" });
  const sections = await page.evaluate(() =>
    [...document.querySelectorAll("main > * , .container > section, .card")].slice(0, 40).map((el) => ({
      cls: (typeof el.className === "string" ? el.className : "").slice(0, 40),
      t: el.innerText.replace(/\s+/g, " ").trim().slice(0, 100),
      y: Math.round(el.getBoundingClientRect().top + window.scrollY),
    })),
  );
  probes.push({ what: "status-sections", sections });
  console.log(`  status sections: ${sections.length}`);
  await ctx.close();
}

await browser.close();
await setState("first");
await writeFile(new URL("../closeups.json", import.meta.url).pathname, JSON.stringify({ probes }, null, 2));
console.log("\ncloseups -> audit/closeups.json");
