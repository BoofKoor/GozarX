// Which end of the hero gradient is which, read from REAL glyph pixels (not from mixing the CSS
// stops and assuming a left→right mapping). For each column strip of the span we take the pixel
// furthest from the ground — that is a glyph pixel — and pair it with the ground measured at the
// same column with the text hidden.

import { chromium } from "playwright";
import { writeFile } from "node:fs/promises";
import { PNG } from "pngjs";

const SITE = "http://127.0.0.1:3100";
const OUT = "/tmp/claude-0/-home-user-GozarX/c019534b-02b6-53f9-aaf3-f0202784f44e/scratchpad/out";
const lin = (c) => { c /= 255; return c <= 0.04045 ? c / 12.92 : Math.pow((c + 0.055) / 1.055, 2.4); };
const L = ([r, g, b]) => 0.2126 * lin(r) + 0.7152 * lin(g) + 0.0722 * lin(b);
const ratio = (a, b) => { const l1 = L(a), l2 = L(b); const [hi, lo] = l1 > l2 ? [l1, l2] : [l2, l1]; return Math.round(((hi + 0.05) / (lo + 0.05)) * 100) / 100; };
const hex = ([r, g, b]) => "#" + [r, g, b].map((v) => Math.round(v).toString(16).padStart(2, "0")).join("");

const run = async () => {
  const browser = await chromium.launch({ executablePath: "/opt/pw-browsers/chromium-1194/chrome-linux/chrome" });
  const res = {};
  for (const theme of ["dark", "light"]) {
    const ctx = await browser.newContext({
      viewport: { width: 390, height: 780 }, deviceScaleFactor: 1, isMobile: true,
      locale: "fa-IR", extraHTTPHeaders: { "accept-language": "fa-IR,fa;q=0.9" }, colorScheme: theme,
    });
    await ctx.addCookies([{ name: "theme", value: theme, url: SITE }, { name: "locale", value: "fa", url: SITE }]);
    const page = await ctx.newPage();
    await page.goto(`${SITE}/`, { waitUntil: "networkidle", timeout: 45000 }).catch(() => {});
    await page.evaluate(() => document.fonts?.ready);
    await page.addStyleTag({ content: "*{animation:none !important;transition:none !important}" });
    await page.waitForTimeout(400);
    const box = await page.locator(".hero-copy h1 .grad").boundingBox();
    const clip = { x: Math.round(box.x), y: Math.round(box.y), width: Math.round(box.width), height: Math.round(box.height) };
    const on = PNG.sync.read(await page.screenshot({ clip }));
    await page.evaluate(() => document.querySelector(".hero-copy h1 .grad").style.setProperty("visibility", "hidden", "important"));
    await page.waitForTimeout(120);
    const off = PNG.sync.read(await page.screenshot({ clip }));
    await page.evaluate(() => document.querySelector(".hero-copy h1 .grad").style.removeProperty("visibility"));

    const cols = [];
    const step = Math.max(1, Math.floor(on.width / 12));
    for (let x = 2; x < on.width - 2; x += step) {
      let glyph = null, best = -1, ground = null;
      for (let y = 0; y < on.height; y++) {
        const i = (on.width * y + x) * 4;
        const p = [on.data[i], on.data[i + 1], on.data[i + 2]];
        const g = [off.data[i], off.data[i + 1], off.data[i + 2]];
        const dist = Math.abs(p[0] - g[0]) + Math.abs(p[1] - g[1]) + Math.abs(p[2] - g[2]);
        if (dist > best) { best = dist; glyph = p; ground = g; }
      }
      if (best < 25) continue; // no glyph in this column
      cols.push({ xFromLeft: x, xPctOfSpan: Math.round((x / on.width) * 100),
                  glyph: hex(glyph), ground: hex(ground), ratio: ratio(glyph, ground) });
    }
    res[theme] = { spanBox: clip, cols,
      worst: cols.reduce((a, b) => (a.ratio <= b.ratio ? a : b)),
      best: cols.reduce((a, b) => (a.ratio >= b.ratio ? a : b)) };
    await ctx.close();
  }
  await browser.close();
  await writeFile(`${OUT}/gradient-pixels.json`, JSON.stringify(res, null, 2));
  for (const t of ["dark", "light"]) {
    console.log(`\n===== ${t} — hero gradient span, real glyph pixels (span box ${res[t].spanBox.width}x${res[t].spanBox.height}) =====`);
    console.log("  visual-LEFT → visual-RIGHT   (Persian reads RIGHT → LEFT)");
    for (const c of res[t].cols)
      console.log(`   x=${String(c.xPctOfSpan).padStart(3)}%  glyph ${c.glyph}  on ground ${c.ground}  → ${String(c.ratio).padStart(5)} ${c.ratio >= 3 ? "" : " **FAIL 3:1**"}`);
    console.log(`  worst: ${res[t].worst.ratio}:1 at x=${res[t].worst.xPctOfSpan}% (${res[t].worst.glyph});  best: ${res[t].best.ratio}:1 at x=${res[t].best.xPctOfSpan}% (${res[t].best.glyph})`);
  }
};
run();
