// Phase 1 — resilience and threshold probes. READ-ONLY.
// The Iranian network case: slow, lossy, and sometimes a request that simply never returns. Three
// questions the earlier walk raised but could not answer:
//   1. how long does the widget sit on its skeleton before it says anything?
//   2. if a request NEVER resolves, does the skeleton ever give up? (useSite.ts has no timeout and
//      no AbortController — this measures whether that matters.)
//   3. what does the returning user see when the device is offline but the page is cached?

import { chromium } from "playwright";
import { writeFile } from "node:fs/promises";

const SITE = "http://127.0.0.1:3100";
const MOCK = "http://127.0.0.1:8000";
const OUT = new URL("../screens/", import.meta.url).pathname;
const ANDROID_UA =
  "Mozilla/5.0 (Linux; Android 12; SM-A125F) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Mobile Safari/537.36";

const probes = [];
const setState = (n) =>
  fetch(`${MOCK}/__state`, { method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify({ name: n }) });

async function phone(browser) {
  const ctx = await browser.newContext({
    viewport: { width: 360, height: 640 }, deviceScaleFactor: 2, isMobile: true, hasTouch: true,
    userAgent: ANDROID_UA, locale: "fa-IR", extraHTTPHeaders: { "accept-language": "fa-IR,fa;q=0.9" },
  });
  await ctx.addCookies([
    { name: "locale", value: "fa", url: SITE },
    { name: "theme", value: "dark", url: SITE },
  ]);
  return ctx;
}

const browser = await chromium.launch({ executablePath: "/opt/pw-browsers/chromium-1194/chrome-linux/chrome" });

// --- 1. a request that NEVER resolves -----------------------------------------------------------
// /status is hung indefinitely. useSite.bootstrap awaits it with no timeout, so `loading` never
// clears. 30 seconds is far beyond any threshold a user would wait through.
{
  await setState("first");
  const ctx = await phone(browser);
  const page = await ctx.newPage();
  await page.route("**/api/public/status*", () => { /* deliberately never fulfilled */ });
  const t0 = Date.now();
  page.goto(SITE + "/", { waitUntil: "domcontentloaded", timeout: 60000 }).catch(() => {});
  const timeline = [];
  for (const at of [1000, 3000, 5000, 10000, 20000, 30000]) {
    while (Date.now() - t0 < at) await page.waitForTimeout(120);
    const s = await page.evaluate(() => ({
      skeleton: !!document.querySelector(".skeleton"),
      widgetText: document.querySelector(".widget")?.innerText.replace(/\s+/g, " ").trim().slice(0, 90) ?? null,
      anyError: /وقفه|خطا|تلاش دوباره/.test(document.body.innerText),
      ariaBusy: !!document.querySelector("[aria-busy=true]"),
    })).catch(() => ({ crashed: true }));
    timeline.push({ atMs: at, ...s });
    console.log(`  hung /status @${at}ms: skeleton=${s.skeleton} error=${s.anyError} text="${(s.widgetText || "").slice(0, 40)}"`);
    if (at === 10000 || at === 30000) await page.screenshot({ path: OUT + `w-res-hung-${at}ms.png` }).catch(() => {});
  }
  probes.push({ what: "hung-status", timeline });
  await ctx.close();
}

// --- 2. the honest slow-network timeline (throttle + the mock's 3s per call) ---------------------
{
  await setState("slow");
  const ctx = await phone(browser);
  const page = await ctx.newPage();
  const cdp = await ctx.newCDPSession(page);
  await cdp.send("Network.enable");
  await cdp.send("Network.emulateNetworkConditions", { offline: false, latency: 400, downloadThroughput: (400 * 1024) / 8, uploadThroughput: (400 * 1024) / 8 });
  const t0 = Date.now();
  page.goto(SITE + "/", { waitUntil: "domcontentloaded", timeout: 90000 }).catch(() => {});
  const timeline = [];
  let firstWidget = null;
  for (let i = 0; i < 300; i++) {
    await page.waitForTimeout(200);
    const at = Date.now() - t0;
    const s = await page.evaluate(() => ({
      skeleton: !!document.querySelector(".skeleton"),
      picker: !!document.querySelector(".loc-grid"),
      cta: !!document.querySelector("button.btn.cta"),
      bodyLen: document.body ? document.body.innerText.length : 0,
    })).catch(() => null);
    if (!s) continue;
    if (s.picker && firstWidget === null) { firstWidget = at; break; }
    if (at > 40000) break;
  }
  probes.push({ what: "slow-network", firstInteractivePickerMs: firstWidget, note: "400kbps/400ms + the mock's 3s per API call" });
  console.log(`\n  slow network: picker interactive at ${firstWidget}ms`);
  await page.screenshot({ path: OUT + "w-res-slow-settled.png" }).catch(() => {});
  await ctx.close();
}

// --- 3. offline, on a device that has been here before ------------------------------------------
{
  await setState("delivered");
  const ctx = await phone(browser);
  const page = await ctx.newPage();
  await page.goto(SITE + "/", { waitUntil: "networkidle", timeout: 45000 });
  await page.waitForTimeout(1200); // let the service worker install
  await ctx.setOffline(true);
  await page.reload({ waitUntil: "domcontentloaded", timeout: 25000 }).catch((e) => console.log(`  offline reload: ${String(e).split("\n")[0].slice(0, 80)}`));
  await page.waitForTimeout(2500);
  await page.screenshot({ path: OUT + "w-res-offline-reload.png" }).catch(() => {});
  const off = await page.evaluate(() => ({
    url: location.pathname,
    text: document.body.innerText.replace(/\s+/g, " ").trim().slice(0, 300),
    hasConfigLink: /vless:\/\//.test(document.body.innerText),
    hasWidget: !!document.querySelector(".widget"),
  })).catch(() => ({ crashed: true }));
  probes.push({ what: "offline-reload", ...off });
  console.log(`\n  offline reload: url=${off.url} hasConfigLink=${off.hasConfigLink}`);
  console.log(`    text: ${(off.text || "").slice(0, 200)}`);
  await ctx.close();
}

// --- 4. Turnstile: the CTA gated behind a script that Iran cannot reach --------------------------
{
  await setState("turnstile");
  const ctx = await phone(browser);
  const page = await ctx.newPage();
  await page.goto(SITE + "/", { waitUntil: "domcontentloaded", timeout: 30000 }).catch(() => {});
  await page.waitForTimeout(6000); // give the CF script every chance to fail
  await page.screenshot({ path: OUT + "w-res-turnstile.png" }).catch(() => {});
  const ts = await page.evaluate(() => {
    const cta = document.querySelector("button.btn.cta");
    return {
      ctaDisabled: cta ? cta.disabled : null,
      ctaText: cta ? cta.innerText.replace(/\s+/g, " ").trim() : null,
      failNotice: document.querySelector(".ts-fail")?.innerText.replace(/\s+/g, " ").trim() ?? null,
      bodyMentions: /بررسی امنیتی|ربات/.test(document.body.innerText),
    };
  });
  probes.push({ what: "turnstile", ...ts });
  console.log(`\n  turnstile: ctaDisabled=${ts.ctaDisabled} failNotice="${ts.failNotice}"`);
  await ctx.close();
}

// --- 5. the contact form: the only place a user types --------------------------------------------
{
  await setState("first");
  const ctx = await phone(browser);
  const page = await ctx.newPage();
  await page.goto(SITE + "/contact", { waitUntil: "networkidle", timeout: 45000 });
  const form = await page.evaluate(() => ({
    fields: [...document.querySelectorAll("input, textarea, select")].map((el) => ({
      name: el.name || el.id, type: el.type || el.tagName.toLowerCase(),
      required: el.required, placeholder: el.placeholder || null,
      label: (() => { const l = document.querySelector(`label[for="${el.id}"]`); return l ? l.innerText.trim() : null; })(),
      h: Math.round(el.getBoundingClientRect().height),
    })),
    submit: [...document.querySelectorAll("button[type=submit], form button")].map((b) => b.innerText.trim()),
    text: document.body.innerText.replace(/\s+/g, " ").trim().slice(0, 400),
  }));
  probes.push({ what: "contact-form", ...form });
  console.log(`\n  contact form: ${JSON.stringify(form.fields)}`);
  // submit empty — what does the error say?
  await page.locator("form button, button[type=submit]").first().click({ timeout: 6000 }).catch(() => {});
  await page.waitForTimeout(800);
  await page.screenshot({ path: OUT + "w-res-contact-empty-submit.png" });
  const err = await page.evaluate(() => ({
    alerts: [...document.querySelectorAll("[role=alert], .err, .error, .field-err")].map((e) => e.innerText.trim()),
    invalid: [...document.querySelectorAll(":invalid")].map((e) => e.tagName + ":" + (e.name || e.id)),
  }));
  probes.push({ what: "contact-empty-submit", ...err });
  console.log(`  empty submit: alerts=${JSON.stringify(err.alerts)} invalid=${JSON.stringify(err.invalid)}`);
  await ctx.close();
}

await browser.close();
await setState("first");
await writeFile(new URL("../resilience.json", import.meta.url).pathname, JSON.stringify({ probes }, null, 2));
console.log("\nresilience -> audit/resilience.json");
