// §4.3 — what /status actually renders for a visitor with NO prior state (the state a freshly
// installed PWA would open into if start_url pointed there). Fresh context, no cookies, no
// localStorage, mock reset to `first`.

import { chromium } from "playwright";
import { writeFile } from "node:fs/promises";

const SITE = "http://127.0.0.1:3100";
const OUT = "/tmp/claude-0/-home-user-GozarX/c019534b-02b6-53f9-aaf3-f0202784f44e/scratchpad/out";

const run = async () => {
  await fetch("http://127.0.0.1:8000/__state", {
    method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify({ name: "first" }),
  });
  const browser = await chromium.launch({ executablePath: "/opt/pw-browsers/chromium-1194/chrome-linux/chrome" });
  const out = {};
  for (const [label, path] of [["status-fresh", "/status"], ["home-fresh", "/"]]) {
    const ctx = await browser.newContext({
      viewport: { width: 390, height: 780 }, deviceScaleFactor: 2, isMobile: true, hasTouch: true,
      locale: "fa-IR", extraHTTPHeaders: { "accept-language": "fa-IR,fa;q=0.9" }, colorScheme: "dark",
    });
    const page = await ctx.newPage();
    await page.goto(`${SITE}${path}`, { waitUntil: "networkidle", timeout: 45000 }).catch(() => {});
    await page.evaluate(() => document.fonts?.ready);
    await page.waitForTimeout(1500);
    out[label] = await page.evaluate(() => {
      const txt = (document.querySelector("main") || document.body).innerText;
      const btns = [...document.querySelectorAll("main a[href], main button")]
        .filter((b) => b.getBoundingClientRect().width > 0)
        .map((b) => (b.textContent || "").trim().slice(0, 34)).filter(Boolean);
      return {
        title: document.title,
        h1: (document.querySelector("h1") || {}).textContent,
        docHeight: document.documentElement.scrollHeight,
        firstScreen: txt.split("\n").filter((l) => l.trim()).slice(0, 22),
        interactiveCount: btns.length,
        interactive: btns.slice(0, 20),
        hasLoginForm: !!document.querySelector('input[type=password], form[action*=login]'),
        hasEmptyState: !!document.querySelector(".empty, .center-state, .state-art"),
        emptyStateText: [...document.querySelectorAll(".empty, .center-state")].map((e) => e.innerText.trim().slice(0, 120)),
        skeletons: document.querySelectorAll(".skeleton, .wskel, .rw2-skel").length,
        claimWidgetPresent: !!document.querySelector(".widget"),
        configLinkPresent: !!document.querySelector(".copyfield code"),
      };
    });
    await page.screenshot({ path: `${OUT}/${label}.png`, fullPage: true });
    await ctx.close();
  }
  await browser.close();
  await writeFile(`${OUT}/status-fresh.json`, JSON.stringify(out, null, 2));
  console.log(JSON.stringify(out, null, 2));
};
run();
