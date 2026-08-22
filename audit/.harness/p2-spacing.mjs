// A1 follow-up: where does the *felt* vertical cost at a section boundary actually come from?
// Measures, per boundary: last ink of section N → first ink of N+1 (the head), and → the first
// ink of N+1's BODY (past the .sec-head block). Also breaks the .sec-head stack into its parts.

import { chromium } from "playwright";
import { writeFile } from "node:fs/promises";

const SITE = "http://127.0.0.1:3100";
const OUT = "/tmp/claude-0/-home-user-GozarX/c019534b-02b6-53f9-aaf3-f0202784f44e/scratchpad/out";
const WIDTHS = [360, 390, 412, 591];

const probe = () => {
  const px = (v) => Math.round(v * 10) / 10;
  const abs = (el) => { const r = el.getBoundingClientRect(); return { t: px(r.top + scrollY), b: px(r.bottom + scrollY), h: px(r.height) }; };
  const lastInk = (root) => {
    let m = null;
    for (const el of root.querySelectorAll("*")) {
      const r = el.getBoundingClientRect();
      if (r.height <= 0 || r.width <= 0) continue;
      const style = getComputedStyle(el);
      if (style.visibility === "hidden" || style.opacity === "0") continue;
      const hasInk = [...el.childNodes].some((n) => n.nodeType === 3 && n.textContent.trim()) ||
        el.tagName === "IMG" || el.tagName === "SVG" || el.tagName === "svg" ||
        (style.backgroundColor !== "rgba(0, 0, 0, 0)" && el.className !== "sec");
      if (!hasInk) continue;
      const b = r.bottom + scrollY;
      if (!m || b > m.b) m = { b: px(b), el: el.tagName + "." + String(el.className).slice(0, 30) };
    }
    return m;
  };
  const secs = [...document.querySelectorAll("main section")];
  const rows = [];
  for (let i = 1; i < secs.length; i++) {
    const prev = secs[i - 1], cur = secs[i];
    const head = cur.querySelector(".sec-head");
    const body = [...cur.children[0].children].find((c) => !c.classList.contains("sec-head"));
    const pi = lastInk(prev);
    rows.push({
      boundary: `${prev.id || prev.className}→${cur.id || cur.className}`,
      prevLastInk: pi ? pi.b : null,
      prevLastInkEl: pi ? pi.el : null,
      curBoxTop: abs(cur).t,
      headTop: head ? abs(head).t : null,
      headHeight: head ? abs(head).h : null,
      headMarginBottom: head ? getComputedStyle(head).marginBottom : null,
      bodyTop: body ? abs(body).t : null,
      inkToHead: head && pi ? px(abs(head).t - pi.b) : null,
      inkToBody: body && pi ? px(abs(body).t - pi.b) : null,
      headParts: head ? [...head.children].map((c) => ({
        cls: c.className, h: px(c.getBoundingClientRect().height),
        mb: getComputedStyle(c).marginBottom, fs: getComputedStyle(c).fontSize,
        lines: Math.round(c.getBoundingClientRect().height / parseFloat(getComputedStyle(c).lineHeight)),
      })) : null,
    });
  }
  return { rows, viewport: innerWidth, doc: document.documentElement.scrollHeight };
};

const run = async () => {
  const browser = await chromium.launch({ executablePath: "/opt/pw-browsers/chromium-1194/chrome-linux/chrome" });
  const all = {};
  for (const width of WIDTHS) {
    const ctx = await browser.newContext({
      viewport: { width, height: 780 }, deviceScaleFactor: 2, isMobile: true, hasTouch: true,
      locale: "fa-IR", extraHTTPHeaders: { "accept-language": "fa-IR,fa;q=0.9" }, colorScheme: "dark",
    });
    await ctx.addCookies([{ name: "theme", value: "dark", url: SITE }, { name: "locale", value: "fa", url: SITE }]);
    const page = await ctx.newPage();
    await page.goto(`${SITE}/`, { waitUntil: "networkidle", timeout: 45000 }).catch(() => {});
    await page.evaluate(async () => {
      for (let y = 0; y < document.body.scrollHeight; y += 600) { scrollTo(0, y); await new Promise(r => setTimeout(r, 40)); }
      scrollTo(0, 0); await new Promise(r => setTimeout(r, 200));
    });
    await page.evaluate(() => document.fonts?.ready);
    await page.waitForTimeout(300);
    all[width] = await page.evaluate(probe);
    await ctx.close();
  }
  await browser.close();
  await writeFile(`${OUT}/spacing.json`, JSON.stringify(all, null, 2));
  for (const w of WIDTHS) {
    console.log(`\n== ${w}px (doc ${all[w].doc}) ==`);
    for (const r of all[w].rows) {
      console.log(`  ${r.boundary.padEnd(30)} inkToHead=${String(r.inkToHead).padStart(6)}  inkToBody=${String(r.inkToBody).padStart(6)}  headH=${String(r.headHeight).padStart(6)} mb=${r.headMarginBottom}`);
    }
    const hp = all[w].rows.find((r) => r.headParts)?.headParts;
    if (hp) console.log("  head parts:", JSON.stringify(hp));
  }
};
run();
