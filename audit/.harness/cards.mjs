// Phase 1 — tall-element crops. READ-ONLY. A 360×640 viewport clips any crop taller than 640px
// (Playwright's clip is viewport-relative), which silently truncated the delivered config card at
// its halfway point. Rendering at 360 CSS px wide but a tall viewport keeps the MOBILE layout while
// letting the whole card land in one shot.

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

async function ctxFor(browser, locale = "fa", theme = "dark") {
  const ctx = await browser.newContext({
    viewport: { width: 360, height: 1600 }, deviceScaleFactor: 2, isMobile: true, hasTouch: true,
    userAgent: ANDROID_UA, locale: locale === "fa" ? "fa-IR" : "en-US",
    extraHTTPHeaders: { "accept-language": locale === "fa" ? "fa-IR,fa;q=0.9" : "en-US,en;q=0.9" },
  });
  await ctx.addCookies([
    { name: "locale", value: locale, url: SITE },
    { name: "theme", value: theme, url: SITE },
  ]);
  return ctx;
}

async function shotEl(page, sel, file, pad = 10) {
  await page.evaluate(() => document.fonts?.ready).catch(() => {});
  await page.waitForTimeout(250);
  const el = page.locator(sel).first();
  if (!(await el.count())) return { file, missing: sel };
  await el.scrollIntoViewIfNeeded().catch(() => {});
  await page.waitForTimeout(150);
  const box = await el.boundingBox();
  if (!box) return { file, missing: "no box" };
  await page.screenshot({
    path: OUT + file,
    clip: { x: Math.max(0, box.x - pad), y: Math.max(0, box.y - pad), width: Math.min(box.width + pad * 2, 360), height: box.height + pad * 2 },
  });
  console.log(`  ${file}  ${Math.round(box.width)}×${Math.round(box.height)}`);
  return { file, w: Math.round(box.width), h: Math.round(box.height) };
}

const browser = await chromium.launch({ executablePath: "/opt/pw-browsers/chromium-1194/chrome-linux/chrome" });
await mkdir(OUT, { recursive: true });

// 1. the delivered config card — the hand-off moment — in both locales
for (const locale of ["fa", "en"]) {
  await setState("delivered");
  const ctx = await ctxFor(browser, locale);
  const page = await ctx.newPage();
  await page.goto(SITE + "/", { waitUntil: "networkidle", timeout: 45000 });
  probes.push({ what: "config-card", locale, ...(await shotEl(page, ".widget", `w-cu2-config-${locale}.png`)) });
  await ctx.close();
}

// 2. the idle picker + CTA
{
  await setState("first");
  const ctx = await ctxFor(browser);
  const page = await ctx.newPage();
  await page.goto(SITE + "/", { waitUntil: "networkidle", timeout: 45000 });
  probes.push({ what: "idle-picker", ...(await shotEl(page, ".widget", "w-cu2-picker-fa.png")) });
  // the hero, so the cold read is legible
  probes.push({ what: "hero", ...(await shotEl(page, ".hero-copy", "w-cu2-hero-fa.png")) });
  await ctx.close();
}

// 3. every error / limit widget
for (const [state, slug, needsClick] of [
  ["cooldown", "cooldown", false],
  ["exhausted", "exhausted", false],
  ["panel_error", "panel-error", false],
  ["no_locations", "no-locations", false],
  ["rate_limited", "rate-limited", true],
  ["location_unavailable", "loc-unavailable", true],
]) {
  await setState(state);
  const ctx = await ctxFor(browser);
  const page = await ctx.newPage();
  await page.goto(SITE + "/", { waitUntil: state === "panel_error" ? "domcontentloaded" : "networkidle", timeout: 30000 }).catch(() => {});
  await page.waitForTimeout(state === "panel_error" ? 2500 : 900);
  if (needsClick) {
    await page.locator("button.btn.cta").first().click({ timeout: 8000 }).catch(() => {});
    await page.waitForTimeout(1600);
  }
  probes.push({ what: state, ...(await shotEl(page, ".widget", `w-cu2-${slug}.png`)) });
  await ctx.close();
}

// 4. the open nav drawer, and the footer's language row
{
  await setState("delivered");
  const ctx = await ctxFor(browser);
  const page = await ctx.newPage();
  await page.goto(SITE + "/", { waitUntil: "networkidle", timeout: 45000 });
  await page.locator("header button[aria-expanded]").first().click({ timeout: 6000 }).catch(() => {});
  await page.waitForTimeout(600);
  await page.screenshot({ path: OUT + "w-cu2-drawer.png", clip: { x: 0, y: 0, width: 360, height: 640 } });
  console.log("  w-cu2-drawer.png");
  probes.push({ what: "drawer" });
  await ctx.close();
}
{
  await setState("first");
  const ctx = await ctxFor(browser);
  const page = await ctx.newPage();
  await page.goto(SITE + "/", { waitUntil: "networkidle", timeout: 45000 });
  probes.push({ what: "footer", ...(await shotEl(page, "footer", "w-cu2-footer.png")) });
  await ctx.close();
}

// 5. the status page's account card
{
  await setState("delivered");
  const ctx = await ctxFor(browser);
  const page = await ctx.newPage();
  await page.goto(SITE + "/status", { waitUntil: "networkidle", timeout: 45000 });
  await page.evaluate(async () => {
    const s = Math.floor(window.innerHeight * 0.8);
    for (let y = 0; y < document.body.scrollHeight; y += s) { window.scrollTo(0, y); await new Promise((r) => setTimeout(r, 60)); }
    window.scrollTo(0, 0);
  });
  await page.waitForTimeout(400);
  await page.screenshot({ path: OUT + "w-cu2-status-full.png", fullPage: true });
  console.log("  w-cu2-status-full.png");
  const cards = await page.evaluate(() =>
    [...document.querySelectorAll(".card, section")].map((el) => ({
      cls: (typeof el.className === "string" ? el.className : "").slice(0, 50),
      h: Math.round(el.getBoundingClientRect().height),
      y: Math.round(el.getBoundingClientRect().top + window.scrollY),
      t: el.innerText.replace(/\s+/g, " ").trim().slice(0, 140),
    })),
  );
  probes.push({ what: "status-cards", cards });
  console.log(`  status cards:\n${cards.map((c) => `    y=${c.y} .${c.cls} — ${c.t}`).join("\n")}`);
  await ctx.close();
}

await browser.close();
await setState("first");
await writeFile(new URL("../cards.json", import.meta.url).pathname, JSON.stringify({ probes }, null, 2));
console.log("\ncards -> audit/cards.json");
