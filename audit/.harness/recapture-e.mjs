// Re-runs only the captures affected by the filename collision fixed in capture.mjs:
//   - Layer E offline + throttled shots, now tagged so they no longer overwrite anything
//   - the Layer A / Layer D shots those had clobbered
// Everything else from the main run is untouched.

import { chromium } from "playwright";

const SITE = "http://127.0.0.1:3100";
const MOCK = "http://127.0.0.1:8000";
const OUT = new URL("../screens/", import.meta.url).pathname;
const ROUTES = { home: "/", status: "/status", locations: "/locations" };

const setState = (name) =>
  fetch(`${MOCK}/__state`, { method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify({ name }) });

async function settle(page) {
  try {
    await page.evaluate(async () => {
      const step = Math.floor(window.innerHeight * 0.8);
      for (let y = 0; y < document.body.scrollHeight; y += step) { window.scrollTo(0, y); await new Promise((r) => setTimeout(r, 60)); }
      window.scrollTo(0, 0); await new Promise((r) => setTimeout(r, 120));
    });
    await page.evaluate(() => document.fonts?.ready);
  } catch {}
  await page.waitForTimeout(250);
}

const browser = await chromium.launch({ executablePath: "/opt/pw-browsers/chromium-1194/chrome-linux/chrome" });

async function shoot({ name, state, tag, offline = false, throttle = false, wait = "networkidle" }) {
  await setState(state);
  const ctx = await browser.newContext({
    viewport: { width: 360, height: 640 }, deviceScaleFactor: 2, isMobile: true, hasTouch: true,
    locale: "fa-IR", extraHTTPHeaders: { "accept-language": "fa-IR,fa;q=0.9" },
  });
  await ctx.addCookies([
    { name: "locale", value: "fa", url: SITE },
    { name: "theme", value: "dark", url: SITE },
  ]);
  const page = await ctx.newPage();
  if (throttle) {
    const cdp = await ctx.newCDPSession(page);
    await cdp.send("Network.enable");
    await cdp.send("Network.emulateNetworkConditions", { offline: false, latency: 400, downloadThroughput: (400 * 1024) / 8, uploadThroughput: (400 * 1024) / 8 });
  }
  let note = "";
  try {
    if (offline) {
      await page.goto(SITE + ROUTES.home, { waitUntil: "networkidle", timeout: 45000 });
      await ctx.setOffline(true);
      await page.goto(SITE + ROUTES[name], { waitUntil: "domcontentloaded", timeout: 20000 }).catch((e) => { note = String(e).split("\n")[0].slice(0, 120); });
    } else {
      await page.goto(SITE + ROUTES[name], { waitUntil: wait, timeout: 45000 });
      if (wait !== "domcontentloaded") await settle(page);
    }
  } catch (e) { note = String(e).split("\n")[0].slice(0, 120); }
  const file = `fa-360-${name}-dark-${state}${tag ? "-" + tag : ""}.png`;
  await page.screenshot({ path: OUT + file, fullPage: !offline });
  console.log(`  ${file}${note ? "  !! " + note : ""}`);
  await ctx.close();
}

console.log("Layer E (tagged)");
for (const name of ["home", "status", "locations"]) {
  await shoot({ name, state: "slow", tag: "slow3g", throttle: true, wait: "domcontentloaded" });
  await shoot({ name, state: "first", tag: "offline", offline: true });
}

console.log("restoring the shots the collision had overwritten");
for (const name of ["home", "status", "locations"]) {
  await shoot({ name, state: "first" });                            // Layer A
}
for (const name of ["home", "status"]) {
  await shoot({ name, state: "slow", wait: "domcontentloaded" });    // Layer D
}

await browser.close();
await setState("first");
console.log("done");
