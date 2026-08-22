// Gate 2 · item 2 — the CTA fold target, stated against its BOTTOM edge.
//
// The addendum's target: CTA bottom at 718 - 16 = 702. Every candidate removal below is measured
// by how far it moves the CTA's BOTTOM, not by how much it removes from the document — those are
// different numbers, and the picker change is the case that proves it (it moves the CTA without
// shortening the page at all).

import { chromium } from "playwright";
import { writeFile } from "node:fs/promises";

const SITE = "http://127.0.0.1:3100";
const OUT = "/tmp/claude-0/-home-user-GozarX/c019534b-02b6-53f9-aaf3-f0202784f44e/scratchpad/out";
const FOLD = 718, MARGIN = 16, TARGET = FOLD - MARGIN;
const WIDTHS = [360, 390, 393, 412];

const CANDIDATES = {
  "baseline": "",
  "hero padding-block 28→12 top": "#app .hero{ padding-block:12px 44px !important }",
  "h1 margin 4/16 → 0/10": "#app .hero-copy h1{ margin:0 0 10px !important }",
  "hero .sub margin-bottom 22→14": "#app .hero-copy .sub{ margin-block-end:14px !important }",
  "hero .sub font 17→15.5px": "#app .hero-copy .sub{ font-size:15.5px !important }",
  "trust-row hidden below 940px": "@media (max-width:939px){ #app .trust-row{ display:none !important } }",
  "widget padding 24→18": "#app #hero-widget .widget{ padding:18px !important }",
  "w-head margin-bottom 20→12": "#app .w-head{ margin-block-end:12px !important }",
  "picker max-height 268→196 (1.5 rows)": "#app .loc-scroll > .loc-grid{ max-block-size:196px !important }",
  "picker max-height 268→160 (1 row + peek)": "#app .loc-scroll > .loc-grid{ max-block-size:160px !important }",
  "cta-wrap margin-top 20→14": "#app .cta-wrap{ margin-block-start:14px !important }",
  "widget min-block-size 610→auto": "#app #hero-widget .widget{ min-block-size:0 !important }",
};

// The combination that actually reaches the target, assembled from the cheapest items first.
const COMBO = [
  "hero padding-block 28→12 top",
  "h1 margin 4/16 → 0/10",
  "hero .sub margin-bottom 22→14",
  "widget padding 24→18",
  "w-head margin-bottom 20→12",
  "cta-wrap margin-top 20→14",
  "picker max-height 268→196 (1.5 rows)",
];

const read = () => {
  const px = (v) => Math.round(v * 10) / 10;
  const c = document.querySelector(".cta").getBoundingClientRect();
  return { top: px(c.top + scrollY), bottom: px(c.bottom + scrollY), h: px(c.height),
           doc: px(document.documentElement.scrollHeight) };
};

const run = async () => {
  const browser = await chromium.launch({ executablePath: "/opt/pw-browsers/chromium-1194/chrome-linux/chrome" });
  const out = { fold: FOLD, margin: MARGIN, target: TARGET, single: {}, combo: {} };

  const measure = async (width, css) => {
    const ctx = await browser.newContext({
      viewport: { width, height: 780 }, deviceScaleFactor: 1, isMobile: true, hasTouch: true,
      locale: "fa-IR", extraHTTPHeaders: { "accept-language": "fa-IR,fa;q=0.9" }, colorScheme: "dark",
    });
    await ctx.addCookies([{ name: "theme", value: "dark", url: SITE }, { name: "locale", value: "fa", url: SITE }]);
    const page = await ctx.newPage();
    await page.goto(`${SITE}/`, { waitUntil: "networkidle", timeout: 45000 }).catch(() => {});
    await page.evaluate(() => document.fonts?.ready);
    if (css) await page.addStyleTag({ content: css });
    await page.evaluate(async () => {
      for (let y = 0; y < document.body.scrollHeight; y += 600) { scrollTo(0, y); await new Promise(r => setTimeout(r, 30)); }
      scrollTo(0, 0); await new Promise(r => setTimeout(r, 150));
    });
    await page.waitForTimeout(250);
    const r = await page.evaluate(read);
    await ctx.close();
    return r;
  };

  for (const [name, css] of Object.entries(CANDIDATES)) {
    out.single[name] = {};
    for (const w of WIDTHS) out.single[name][w] = await measure(w, css);
  }
  const comboCss = COMBO.map((k) => CANDIDATES[k]).join("\n");
  for (const w of WIDTHS) out.combo[w] = await measure(w, comboCss);
  await browser.close();
  await writeFile(`${OUT}/g2-fold.json`, JSON.stringify(out, null, 2));

  const base = out.single["baseline"];
  console.log(`FOLD = ${FOLD}px · required CTA bottom = ${FOLD} - ${MARGIN} = ${TARGET}px\n`);
  console.log("=== the real target, per width ===");
  console.log("width  CTA height  CTA top  CTA bottom   removal needed to seat the BOTTOM at " + TARGET);
  for (const w of WIDTHS) {
    const b = base[w];
    console.log(`${String(w).padStart(5)}  ${String(b.h).padStart(10)}  ${String(b.top).padStart(7)}  ${String(b.bottom).padStart(10)}   ${String(Math.round((b.bottom - TARGET) * 10) / 10).padStart(6)}px`);
  }
  console.log("\n=== how far each candidate moves the CTA's BOTTOM (and the document, for contrast) ===");
  console.log("candidate".padEnd(42) + "Δ CTA bottom @390   Δ doc @390   CTA bottom after");
  for (const [name, per] of Object.entries(out.single)) {
    if (name === "baseline") continue;
    const d = Math.round((base[390].bottom - per[390].bottom) * 10) / 10;
    const dd = Math.round((base[390].doc - per[390].doc) * 10) / 10;
    console.log(`${name.padEnd(42)}${String(d).padStart(11)}px ${String(dd).padStart(12)}px ${String(per[390].bottom).padStart(17)}`);
  }
  console.log("\n=== the combination ===");
  console.log("width  CTA bottom  vs target " + TARGET + "   doc height   verdict");
  for (const w of WIDTHS) {
    const c = out.combo[w], b = base[w];
    const gap = Math.round((c.bottom - TARGET) * 10) / 10;
    console.log(`${String(w).padStart(5)}  ${String(c.bottom).padStart(10)}  ${String(gap > 0 ? "+" + gap : gap).padStart(13)}   ${String(c.doc).padStart(10)}   ${c.bottom <= TARGET ? "ABOVE FOLD" : "still below"}   (was ${b.bottom})`);
  }
};
run();
