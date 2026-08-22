// Gate 2 · item 1 — three hero treatments that differ in KIND, each measured the same way the
// current headline was measured in Gate 1: real glyph pixels at ten columns across the span, paired
// with the ground read at the same column with the text hidden. Reports the MINIMUM (not the mean)
// per theme, plus the ratio over the last word in RTL reading order, which for «در چند ثانیه» is
// «ثانیه» — the visually leftmost word.

import { chromium } from "playwright";
import { writeFile } from "node:fs/promises";
import { PNG } from "pngjs";

const SITE = "http://127.0.0.1:3100";
const OUT = "/tmp/claude-0/-home-user-GozarX/c019534b-02b6-53f9-aaf3-f0202784f44e/scratchpad/out";
const lin = (c) => { c /= 255; return c <= 0.04045 ? c / 12.92 : Math.pow((c + 0.055) / 1.055, 2.4); };
const L = ([r, g, b]) => 0.2126 * lin(r) + 0.7152 * lin(g) + 0.0722 * lin(b);
const ratio = (a, b) => { const l1 = L(a), l2 = L(b); const [hi, lo] = l1 > l2 ? [l1, l2] : [l2, l1]; return Math.round(((hi + 0.05) / (lo + 0.05)) * 100) / 100; };
const hex = ([r, g, b]) => "#" + [r, g, b].map((v) => Math.round(v).toString(16).padStart(2, "0")).join("");

// ---------------------------------------------------------------------------------------------
// The three treatments. Each is the complete CSS that would replace globals.css:214.
// ---------------------------------------------------------------------------------------------
const TREATMENTS = {
  "0 · current (baseline)": "",

  // A — SOLID. No gradient at all. Reuses the existing --brand-tint-ink token, which is already
  // per-theme (#93C5FD dark / #1D4ED8 light) and already used for brand-coloured ink elsewhere,
  // so it adds no new colour to the palette.
  "A · solid brand ink": `
    .hero-copy h1 .grad{
      background:none !important; -webkit-background-clip:border-box !important;
      background-clip:border-box !important; color:var(--brand-tint-ink) !important;
      -webkit-text-fill-color:var(--brand-tint-ink) !important;
    }`,

  // B — GRADIENT KEPT, with two changes: a raised floor so the dark end clears the threshold on the
  // dark ground, and stops that mirror with the reading direction (360-120 = 240deg), matching the
  // six gradients that already do this (globals.css:117, 250, 462, 742, 786, 820).
  "B · gradient, raised floor + RTL-mirrored": `
    #app[data-theme="dark"], #app:not([data-theme="light"]){ --hero-grad-1:#3B82F6; --hero-grad-2:#22D3EE; }
    #app[data-theme="light"]{ --hero-grad-1:#1D4ED8; --hero-grad-2:#0E7490; }
    .hero-copy h1 .grad{
      background:linear-gradient(120deg,var(--hero-grad-1),var(--hero-grad-2)) !important;
      -webkit-background-clip:text !important; background-clip:text !important;
      color:transparent !important; -webkit-text-fill-color:transparent !important;
    }
    [dir="rtl"] .hero-copy h1 .grad{
      background:linear-gradient(240deg,var(--hero-grad-1),var(--hero-grad-2)) !important;
      -webkit-background-clip:text !important; background-clip:text !important;
    }`,

  // C — TYPE, NOT HUE. The emphasis moves to weight and size; the phrase is set in --text (the
  // page's maximum-contrast ink) and the brand colour is demoted to a rule under the words, where
  // it decorates instead of carrying the text.
  "C · weight + size, colour demoted to a rule": `
    #app[data-theme="dark"], #app:not([data-theme="light"]){ --hero-rule:#22D3EE; }
    #app[data-theme="light"]{ --hero-rule:#0E7490; }
    .hero-copy h1 .grad{
      background:linear-gradient(var(--hero-rule),var(--hero-rule)) no-repeat !important;
      background-size:100% 3px !important; background-position:0 92% !important;
      -webkit-background-clip:border-box !important; background-clip:border-box !important;
      color:var(--text) !important; -webkit-text-fill-color:var(--text) !important;
      font-weight:900 !important; font-size:1.14em !important;
      padding-block-end:.10em !important;
    }`,
};

const sampleSpan = async (page, opts = {}) => {
  const box = await page.locator(".hero-copy h1 .grad").boundingBox();
  const clip = { x: Math.round(box.x), y: Math.round(box.y), width: Math.round(box.width), height: Math.round(box.height) };
  // x-range of the LAST WORD IN RTL READING ORDER (visually leftmost run of the span)
  const lastWord = await page.evaluate(() => {
    const g = document.querySelector(".hero-copy h1 .grad");
    const node = [...g.childNodes].find((n) => n.nodeType === 3);
    const text = node.textContent;
    const words = text.trim().split(/\s+/);
    const last = words[words.length - 1];               // reading order: the final word
    const start = text.lastIndexOf(last);
    const r = document.createRange();
    r.setStart(node, start); r.setEnd(node, start + last.length);
    const rect = r.getBoundingClientRect();
    const spanRect = g.getBoundingClientRect();
    return { word: last, leftPct: (rect.left - spanRect.left) / spanRect.width,
             rightPct: (rect.right - spanRect.left) / spanRect.width };
  });
  const on = PNG.sync.read(await page.screenshot({ clip }));
  await page.evaluate(() => document.querySelector(".hero-copy h1 .grad").style.setProperty("visibility", "hidden", "important"));
  await page.waitForTimeout(120);
  const off = PNG.sync.read(await page.screenshot({ clip }));
  await page.evaluate(() => document.querySelector(".hero-copy h1 .grad").style.removeProperty("visibility"));

  // Per column, the STROKE INTERIOR: pixels well clear of the ground, then their median colour.
  // Taking the single most-distant pixel picks antialiased edges in columns that only graze a
  // stem — WCAG evaluates the solid glyph, not its antialiasing, so that reads as a false failure.
  // `yFrom`/`yTo` clip the sampled band so a decorative rule under the words is not measured as
  // if it were text (treatment C draws one); it is measured separately below.
  const med = (arr) => arr.slice().sort((a, b) => a - b)[Math.floor(arr.length / 2)];
  const yFrom = Math.floor(on.height * (opts.yFrom ?? 0));
  const yTo = Math.ceil(on.height * (opts.yTo ?? 1));
  // The core threshold must be anchored to the SPAN's maximum distance, not each column's own.
  // A column that only grazes a stem has a small local max, so a local 75% still selects that
  // column's antialiasing — which is what made a solid colour report a 2.5-5.2 spread.
  let globalMax = 0;
  for (let y = yFrom; y < yTo; y++) {
    for (let x = 0; x < on.width; x++) {
      const i = (on.width * y + x) * 4;
      const d = Math.abs(on.data[i] - off.data[i]) + Math.abs(on.data[i + 1] - off.data[i + 1]) +
                Math.abs(on.data[i + 2] - off.data[i + 2]);
      if (d > globalMax) globalMax = d;
    }
  }
  const cols = [];
  const step = Math.max(1, Math.floor(on.width / 12));
  for (let x = 2; x < on.width - 2; x += step) {
    const px = [];
    let maxD = 0;
    for (let y = yFrom; y < yTo; y++) {
      const i = (on.width * y + x) * 4;
      const p = [on.data[i], on.data[i + 1], on.data[i + 2]];
      const g = [off.data[i], off.data[i + 1], off.data[i + 2]];
      const d = Math.abs(p[0] - g[0]) + Math.abs(p[1] - g[1]) + Math.abs(p[2] - g[2]);
      px.push({ p, g, d });
      if (d > maxD) maxD = d;
    }
    if (maxD < globalMax * 0.6) continue;          // column grazes only antialiasing
    const core = px.filter((q) => q.d >= globalMax * 0.75);
    if (core.length < 2) continue;                 // a single pixel is an edge, not a stroke
    const glyph = [0, 1, 2].map((k) => med(core.map((q) => q.p[k])));
    const ground = [0, 1, 2].map((k) => med(px.map((q) => q.g[k])));
    cols.push({ xPct: Math.round((x / on.width) * 100), glyph: hex(glyph), ground: hex(ground),
                corePx: core.length, ratio: ratio(glyph, ground) });
  }
  const inLastWord = cols.filter((c) => c.xPct / 100 >= lastWord.leftPct - 0.02 && c.xPct / 100 <= lastWord.rightPct + 0.02);
  const type = await page.evaluate(() => {
    const g = getComputedStyle(document.querySelector(".hero-copy h1 .grad"));
    return { fontSize: parseFloat(g.fontSize), fontWeight: Number(g.fontWeight) };
  });
  // WCAG: large text is >=24px, or >=18.66px when bold (>=700)
  const isLarge = type.fontSize >= 24 || (type.fontSize >= 18.66 && type.fontWeight >= 700);
  return {
    fontSize: type.fontSize, fontWeight: type.fontWeight, isLarge, threshold: isLarge ? 3 : 4.5,
    samples: cols.length, cols,
    min: cols.length ? Math.min(...cols.map((c) => c.ratio)) : null,
    max: cols.length ? Math.max(...cols.map((c) => c.ratio)) : null,
    lastWord: lastWord.word,
    lastWordCols: inLastWord.length,
    lastWordMin: inLastWord.length ? Math.min(...inLastWord.map((c) => c.ratio)) : null,
  };
};

const run = async () => {
  const browser = await chromium.launch({ executablePath: "/opt/pw-browsers/chromium-1194/chrome-linux/chrome" });
  const results = {};
  for (const [name, css] of Object.entries(TREATMENTS)) {
    results[name] = {};
    for (const theme of ["dark", "light"]) {
      const ctx = await browser.newContext({
        viewport: { width: 393, height: 820 }, deviceScaleFactor: 1, isMobile: true, hasTouch: true,
        locale: "fa-IR", extraHTTPHeaders: { "accept-language": "fa-IR,fa;q=0.9" }, colorScheme: theme,
      });
      await ctx.addCookies([{ name: "theme", value: theme, url: SITE }, { name: "locale", value: "fa", url: SITE }]);
      const page = await ctx.newPage();
      await page.goto(`${SITE}/`, { waitUntil: "networkidle", timeout: 45000 }).catch(() => {});
      await page.evaluate(() => document.fonts?.ready);
      await page.addStyleTag({ content: "*{animation:none !important;transition:none !important}" });
      if (css) await page.addStyleTag({ content: css });
      await page.waitForTimeout(400);
      results[name][theme] = await sampleSpan(page, name.startsWith("C") ? { yFrom: 0, yTo: 0.80 } : {});
      // visual, at mobile width
      const h1 = page.locator(".hero-copy h1");
      const b = await h1.boundingBox();
      await page.screenshot({
        path: `${OUT}/g3-contrast-${name.split(" ")[0]}-${theme}-393.png`,
        clip: { x: 0, y: Math.max(0, b.y - 18), width: 390, height: b.height + 36 },
      });
      await ctx.close();
    }
  }
  await browser.close();
  await writeFile(`${OUT}/g3-hero-contrast-393.json`, JSON.stringify(results, null, 2));

  for (const [name, r] of Object.entries(results)) {
    console.log(`\n=== ${name} ===`);
    for (const theme of ["dark", "light"]) {
      const t = r[theme];
      const size = `${t.fontSize}px/${t.fontWeight}`;
      const cls = t.isLarge ? `large text (>=24px) -> AA needs ${t.threshold}:1` : `normal text -> AA needs ${t.threshold}:1`;
      const verdict = t.min >= t.threshold ? "PASS" : "**FAIL**";
      const lw = t.lastWordMin >= t.threshold ? "pass" : "**fail**";
      console.log(`  ${theme.padEnd(5)} ${size.padEnd(10)} ${cls}`);
      console.log(`        MIN across ${t.samples} points: ${String(t.min).padStart(6)}:1  ${verdict}     (max ${t.max}:1)`);
      console.log(`        last word in RTL order «${t.lastWord}» (${t.lastWordCols} pts): ${String(t.lastWordMin).padStart(6)}:1  ${lw}`);
    }
  }
};
run();
