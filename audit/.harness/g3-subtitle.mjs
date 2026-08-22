// Gate 3 · item 1 — test the "one taller element" explanation against the addendum's objection.
//
// If a longer hero subtitle is what separates the two baselines, the extra height is extra WRAPPED
// LINES, and a narrower column wraps more of them. So the document-height delta must be monotonic
// in width and LARGEST at 360. The addendum reports 24 @360, 85 @390, 114 @393, 85 @412 — neither
// monotonic nor largest at 360. This measures the delta profile a longer subtitle actually produces.

import { chromium } from "playwright";
import { writeFile } from "node:fs/promises";

const SITE = "http://127.0.0.1:3100";
const OUT = "/tmp/claude-0/-home-user-GozarX/c019534b-02b6-53f9-aaf3-f0202784f44e/scratchpad/out";
const WIDTHS = [360, 390, 393, 412];

// The repo default, verbatim from lib/design-copy.ts:22 (what app/page.tsx:59 falls back to).
const REPO_DEFAULT =
  "هر روز یک کانفیگ آزمایشی رایگان بگیر؛ لوکیشن دلخواهت را انتخاب کن و بدون ثبت‌نام وصل شو. با دعوت دوستان هم حجم روزانه‌ات بیشتر می‌شود.";

// Plausible longer variants an admin might have saved in site_hero_sub.
const EXTRA = [
  "",
  " سرعت بالا و بدون قطعی، روی همهٔ دستگاه‌ها.",
  " سرعت بالا و بدون قطعی، روی همهٔ دستگاه‌ها. هیچ اطلاعات شخصی‌ای از تو نمی‌گیریم.",
  " سرعت بالا و بدون قطعی، روی همهٔ دستگاه‌ها. هیچ اطلاعات شخصی‌ای از تو نمی‌گیریم. پشتیبانی هر روز هفته پاسخگوست.",
];

const read = () => {
  const px = (v) => Math.round(v * 10) / 10;
  const sub = document.querySelector(".hero-copy .sub");
  const s = sub.getBoundingClientRect();
  const cta = document.querySelector(".cta").getBoundingClientRect();
  const lh = parseFloat(getComputedStyle(sub).lineHeight);
  return {
    doc: px(document.documentElement.scrollHeight),
    subH: px(s.height), subLines: Math.round(s.height / lh), lineHeight: px(lh),
    subChars: sub.textContent.trim().length,
    ctaTop: px(cta.top + scrollY), ctaBottom: px(cta.bottom + scrollY),
  };
};

const run = async () => {
  const browser = await chromium.launch({ executablePath: "/opt/pw-browsers/chromium-1194/chrome-linux/chrome" });
  const out = {};
  for (let i = 0; i < EXTRA.length; i++) {
    out[i] = {};
    for (const w of WIDTHS) {
      const ctx = await browser.newContext({
        viewport: { width: w, height: 780 }, deviceScaleFactor: 1, isMobile: true, hasTouch: true,
        locale: "fa-IR", extraHTTPHeaders: { "accept-language": "fa-IR,fa;q=0.9" }, colorScheme: "dark",
      });
      await ctx.addCookies([{ name: "theme", value: "dark", url: SITE }, { name: "locale", value: "fa", url: SITE }]);
      const page = await ctx.newPage();
      await page.goto(`${SITE}/`, { waitUntil: "networkidle", timeout: 45000 }).catch(() => {});
      await page.evaluate(() => document.fonts?.ready);
      if (EXTRA[i]) await page.evaluate((t) => { document.querySelector(".hero-copy .sub").textContent = t; },
                                        REPO_DEFAULT + EXTRA[i]);
      await page.evaluate(async () => {
        for (let y = 0; y < document.body.scrollHeight; y += 600) { scrollTo(0, y); await new Promise(r => setTimeout(r, 30)); }
        scrollTo(0, 0); await new Promise(r => setTimeout(r, 150));
      });
      await page.waitForTimeout(250);
      out[i][w] = await page.evaluate(read);
      await ctx.close();
    }
  }
  await browser.close();
  await writeFile(`${OUT}/g3-subtitle.json`, JSON.stringify(out, null, 2));

  console.log("The repo default, verbatim from lib/design-copy.ts:22:");
  console.log(`  «${REPO_DEFAULT}»`);
  console.log(`  ${REPO_DEFAULT.length} characters\n`);
  console.log("=== subtitle length -> subtitle LINES, per width ===");
  console.log("variant  chars " + WIDTHS.map(w => `${w}px`.padStart(12)).join(""));
  for (let i = 0; i < EXTRA.length; i++)
    console.log(`  +${i}    ${String(out[i][360].subChars).padStart(5)} ` +
      WIDTHS.map(w => `${out[i][w].subLines}L / ${out[i][w].subH}px`.padStart(12)).join(""));
  console.log("\n=== document-height DELTA vs the repo default, per width ===");
  console.log("variant  " + WIDTHS.map(w => `${w}px`.padStart(11)).join("") + "     monotonic & largest at 360?");
  for (let i = 1; i < EXTRA.length; i++) {
    const d = WIDTHS.map(w => Math.round((out[i][w].doc - out[0][w].doc) * 10) / 10);
    const mono = d[0] >= d[1] && d[1] >= d[2] && d[0] === Math.max(...d);
    console.log(`  +${i}    ` + d.map(v => `+${v}`.padStart(11)).join("") + `     ${mono ? "YES" : "no"}`);
  }
  console.log("\n  addendum's reported production deltas:  " +
    ["+24", "+85", "+114", "+85"].map(v => v.padStart(11)).join("") + "     no");
  console.log("\n=== CTA top, per width ===");
  console.log("variant  " + WIDTHS.map(w => `${w}px`.padStart(11)).join(""));
  for (let i = 0; i < EXTRA.length; i++)
    console.log(`  +${i}    ` + WIDTHS.map(w => String(out[i][w].ctaTop).padStart(11)).join(""));
};
run();
