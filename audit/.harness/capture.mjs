// Phase 0 capture harness — read-only. Drives the built site against the mock backend and writes
// full-page screenshots plus a per-capture diagnostics log into audit/.
//
// Layers (see audit/00-recon.md):
//   A  every in-scope route · fa · 360×640 · light+dark
//   B  key routes · en · 360×640 · light+dark
//   C  layout-changing routes · 390/412/768/1440 · fa
//   D  every claim-widget state (S1..S8 + guards) on / and /status
//   E  slow network + offline on the primary path
//   F  targeted close-ups (keyboard open, bidi runs)
//
// Screenshots are taken only AFTER fonts settle and the scroll-reveal observer has fired for every
// section, otherwise a full-page shot captures sections that are still at opacity:0 and the audit
// would be reading its own harness artifacts as design defects.

import { chromium, devices } from "playwright";
import { mkdir, writeFile } from "node:fs/promises";

const SITE = "http://127.0.0.1:3100";
const MOCK = "http://127.0.0.1:8000";
const OUT = new URL("../screens/", import.meta.url).pathname;

const ROUTES = {
  home: "/",
  status: "/status",
  locations: "/locations",
  guides: "/guides",
  "guides-android": "/guides/android",
  "guides-ios": "/guides/ios",
  "guides-windows": "/guides/windows",
  "guides-macos": "/guides/macos",
  "guides-linux": "/guides/linux",
  faq: "/faq",
  about: "/about",
  contact: "/contact",
  privacy: "/privacy",
  terms: "/terms",
  "landing-article": "/l/what-is-vless",
  "landing-location": "/l/free-v2ray-config-germany",
  offline: "/offline",
  notfound: "/this-route-does-not-exist",
};

const KEY_ROUTES = ["home", "status", "locations", "guides", "guides-android", "faq", "contact", "landing-article"];
const LAYOUT_ROUTES = ["home", "status", "locations", "guides", "faq"];

const diagnostics = [];
let shots = 0;

async function setState(name) {
  await fetch(`${MOCK}/__state`, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({ name }),
  });
}

/** Trigger every IntersectionObserver reveal, then return to the top so the full-page shot is honest. */
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
  } catch { /* a page that navigated away mid-settle is not worth failing the run for */ }
  await page.waitForTimeout(250);
}

async function makeContext(browser, { locale, theme, width, height = 640, ua, offline = false }) {
  const ctx = await browser.newContext({
    viewport: { width, height },
    deviceScaleFactor: 2,
    isMobile: width <= 500,
    hasTouch: width <= 500,
    userAgent: ua,
    locale: locale === "fa" ? "fa-IR" : "en-US",
    extraHTTPHeaders: { "accept-language": locale === "fa" ? "fa-IR,fa;q=0.9" : "en-US,en;q=0.9" },
    offline,
  });
  await ctx.addCookies([
    { name: "locale", value: locale, url: SITE },
    { name: "theme", value: theme, url: SITE },
  ]);
  return ctx;
}

/**
 * One capture. `interact` runs after load and before the shot (for states that need a click).
 * `netlog` collects transfer sizes so per-route weight is measured, not guessed.
 */
async function shoot(browser, { name, route, locale, theme, width, height, state = "first", tag, ua, wait = "networkidle", interact, netlog = false, offline = false, throttle }) {
  await setState(state);
  const ctx = await makeContext(browser, { locale, theme, width, height, ua });
  const page = await ctx.newPage();

  const errors = [];
  const resources = [];
  page.on("console", (m) => {
    if (m.type() === "error" || m.type() === "warning") errors.push(`[${m.type()}] ${m.text()}`.slice(0, 300));
  });
  page.on("pageerror", (e) => errors.push(`[pageerror] ${String(e).slice(0, 300)}`));
  page.on("requestfailed", (r) => errors.push(`[requestfailed] ${r.url().slice(0, 160)} — ${r.failure()?.errorText}`));

  // Next serves these responses chunked, so `content-length` is absent on roughly half of them.
  // CDP's `encodedDataLength` is the actual count of bytes that crossed the wire, which is what
  // "first-load JS" has to mean for a user on mobile data.
  let cdp = null;
  if (netlog || throttle) {
    cdp = await ctx.newCDPSession(page);
    await cdp.send("Network.enable");
  }
  if (netlog) {
    const meta = new Map();
    cdp.on("Network.responseReceived", (e) => {
      meta.set(e.requestId, { url: e.response.url.replace(SITE, ""), type: e.type, status: e.response.status });
    });
    cdp.on("Network.loadingFinished", (e) => {
      const m = meta.get(e.requestId);
      if (m) resources.push({ ...m, bytes: e.encodedDataLength });
    });
  }
  if (throttle) {
    await cdp.send("Network.emulateNetworkConditions", {
      offline: false,
      latency: throttle.latency,
      downloadThroughput: throttle.down,
      uploadThroughput: throttle.up,
    });
  }

  let failed = null;
  try {
    if (offline) {
      await page.goto(SITE + ROUTES.home, { waitUntil: "networkidle", timeout: 45000 });
      await ctx.setOffline(true);
      await page.goto(SITE + route, { waitUntil: "domcontentloaded", timeout: 20000 }).catch((e) => {
        errors.push(`[offline-nav] ${String(e).split("\n")[0].slice(0, 200)}`);
      });
    } else {
      await page.goto(SITE + route, { waitUntil: wait, timeout: 45000 });
    }
    if (interact) await interact(page);
    if (wait !== "domcontentloaded" && !offline) await settle(page);
  } catch (e) {
    failed = String(e).split("\n")[0].slice(0, 240);
  }

  // `tag` distinguishes captures that share a state but not a CONDITION — an offline load and a
  // throttled load are both state `first`/`slow`, and without it they overwrite each other and the
  // normal-network shot of the same route.
  const file = `${locale}-${width}-${name}-${theme}-${state}${tag ? "-" + tag : ""}.png`;
  try {
    await page.screenshot({ path: OUT + file, fullPage: !offline });
    shots++;
  } catch (e) {
    failed = (failed ? failed + " | " : "") + "screenshot: " + String(e).split("\n")[0].slice(0, 160);
  }

  // CDP capitalises its resource types (Script/Stylesheet/Font/Image), unlike Playwright's.
  const js = resources.filter((r) => r.type === "Script");
  diagnostics.push({
    file,
    route,
    locale,
    theme,
    width,
    state,
    failed,
    errors,
    ...(netlog
      ? {
          weight: {
            js_requests: js.length,
            js_bytes: js.reduce((s, r) => s + r.bytes, 0),
            css_bytes: resources.filter((r) => r.type === "Stylesheet").reduce((s, r) => s + r.bytes, 0),
            font_bytes: resources.filter((r) => r.type === "Font").reduce((s, r) => s + r.bytes, 0),
            image_bytes: resources.filter((r) => r.type === "Image").reduce((s, r) => s + r.bytes, 0),
            total_bytes: resources.reduce((s, r) => s + r.bytes, 0),
            requests: resources.length,
          },
        }
      : {}),
  });

  await ctx.close();
  process.stdout.write(`  ${file}${failed ? "  !! " + failed : ""}\n`);
}

// --- the matrix --------------------------------------------------------------------------------

// The pre-installed Chromium in this environment (rev 1194) is older than the one this Playwright
// pins, and downloading browsers is not on the table for an audit harness. Point at the binary
// that is already here.
const browser = await chromium.launch({
  executablePath: "/opt/pw-browsers/chromium-1194/chrome-linux/chrome",
});
await mkdir(OUT, { recursive: true });

console.log("Layer A — every route · fa · 360 · light+dark");
for (const [name, route] of Object.entries(ROUTES)) {
  for (const theme of ["light", "dark"]) {
    await shoot(browser, { name, route, locale: "fa", theme, width: 360, netlog: theme === "dark" });
  }
}

console.log("Layer B — key routes · en · 360 · light+dark");
for (const name of KEY_ROUTES) {
  for (const theme of ["light", "dark"]) {
    await shoot(browser, { name, route: ROUTES[name], locale: "en", theme, width: 360 });
  }
}

console.log("Layer C — layout deltas · fa · dark");
for (const name of LAYOUT_ROUTES) {
  for (const [w, h] of [[390, 844], [412, 915], [768, 1024], [1440, 900]]) {
    await shoot(browser, { name, route: ROUTES[name], locale: "fa", theme: "dark", width: w, height: h });
  }
}

console.log("Layer D — claim-widget states on / and /status");
const clickCta = async (page) => {
  const btn = page.locator("button.btn.cta").first();
  if (await btn.count()) {
    await btn.click({ timeout: 5000 }).catch(() => {});
    await page.waitForTimeout(1200);
  }
};
const STATE_SPECS = [
  { state: "first" },
  { state: "delivered" },
  { state: "exhausted" },
  { state: "cooldown" },
  { state: "no_locations" },
  { state: "panel_error" },
  { state: "turnstile" },
  { state: "claim_ok", interact: clickCta },
  { state: "rate_limited", interact: clickCta },
  { state: "location_unavailable", interact: clickCta },
  { state: "slow", wait: "domcontentloaded" }, // catches the loading skeleton
];
for (const spec of STATE_SPECS) {
  for (const name of ["home", "status"]) {
    await shoot(browser, { name, route: ROUTES[name], locale: "fa", theme: "dark", width: 360, ...spec });
  }
}

console.log("Layer E — slow network + offline");
const SLOW = { latency: 400, down: (400 * 1024) / 8, up: (400 * 1024) / 8 };
for (const name of ["home", "status", "locations"]) {
  await shoot(browser, { name, route: ROUTES[name], locale: "fa", theme: "dark", width: 360, state: "slow", tag: "slow3g", throttle: SLOW, wait: "domcontentloaded" });
  await shoot(browser, { name, route: ROUTES[name], locale: "fa", theme: "dark", width: 360, state: "first", tag: "offline", offline: true });
}

console.log("Layer F — targeted close-ups");
// Contact form with the on-screen keyboard occupying the lower half of a 360×640 phone.
await shoot(browser, {
  name: "contact-keyboard", route: ROUTES.contact, locale: "fa", theme: "dark", width: 360, height: 320,
  interact: async (p) => { await p.locator("textarea, input[type=text]").first().focus().catch(() => {}); },
});
// The delivered config card: the vless:// link inside Persian RTL chrome — the bidi case.
for (const locale of ["fa", "en"]) {
  await shoot(browser, { name: "config-card", route: ROUTES.home, locale, theme: "dark", width: 360, state: "delivered" });
}
// Desktop home in both locales, for the cold-Google-entry read.
for (const locale of ["fa", "en"]) {
  await shoot(browser, { name: "home-desktop", route: ROUTES.home, locale, theme: "dark", width: 1440, height: 900 });
}
// A real Telegram Android in-app WebView UA — recorded for reference only; the Telegram surface is
// out of scope by the owner's instruction.
await shoot(browser, {
  name: "home-tg-webview", route: ROUTES.home, locale: "fa", theme: "dark", width: 360,
  ua: "Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 (KHTML, like Gecko) Version/4.0 Chrome/131.0.6778.135 Mobile Safari/537.36",
});

await browser.close();
await setState("first");

await writeFile(
  new URL("../diagnostics.json", import.meta.url).pathname,
  JSON.stringify({ captured: shots, diagnostics }, null, 2),
);
console.log(`\n${shots} screenshots -> audit/screens/`);
console.log(`diagnostics -> audit/diagnostics.json`);
