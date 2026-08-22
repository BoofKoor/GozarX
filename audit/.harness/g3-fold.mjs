// Gate 3 · items 2 and 4.
//   - combination 5 and option 6: CTA TOP and BOTTOM at 360/390/393/412, on the repo baseline.
//   - the smallest hero-subtitle length at which combination 5 clears the fold at 360, found by
//     shortening the subtitle a word at a time and re-measuring — not extrapolated from line height.

import { chromium } from "playwright";
import { writeFile } from "node:fs/promises";

const SITE = "http://127.0.0.1:3100";
const OUT = "/tmp/claude-0/-home-user-GozarX/c019534b-02b6-53f9-aaf3-f0202784f44e/scratchpad/out";
const WIDTHS = [360, 390, 393, 412];
const FOLD = 718, MARGIN = 16, TARGET = FOLD - MARGIN;

const CHROME = `
  #app .hero{ padding-block:12px 44px !important }
  #app .hero-copy h1{ margin:0 0 10px !important }
  #app .hero-copy .sub{ margin-block-end:14px !important }
  #app #hero-widget .widget{ padding:18px !important }
  #app .w-head{ margin-block-end:12px !important }
  #app .cta-wrap{ margin-block-start:14px !important }`;

// Combination 5, rule by rule. It does NOT touch .trust-badges (the trust CARD's three badges near
// the page foot); it hides .trust-row, the four pills under the hero headline.
const COMBO5 = CHROME + `
  #app .loc-scroll > .loc-grid{ max-block-size:160px !important }
  #app .hero-copy .sub{ font-size:15.5px !important }
  @media (max-width:939px){ #app .trust-row{ display:none !important } }`;

const OPTION6 = CHROME + `
  #app .loc-scroll > .loc-grid{ max-block-size:196px !important }
  @media (max-width:939px){ #app .hero-inner{ display:flex; flex-direction:column }
    #app #hero-widget{ order:1 } #app .hero-copy{ order:2; margin-block-start:22px } }`;

const REPO_DEFAULT =
  "هر روز یک کانفیگ آزمایشی رایگان بگیر؛ لوکیشن دلخواهت را انتخاب کن و بدون ثبت‌نام وصل شو. با دعوت دوستان هم حجم روزانه‌ات بیشتر می‌شود.";

const read = () => {
  const px = (v) => Math.round(v * 10) / 10;
  const c = document.querySelector(".cta").getBoundingClientRect();
  const sub = document.querySelector(".hero-copy .sub");
  const s = sub.getBoundingClientRect();
  const lh = parseFloat(getComputedStyle(sub).lineHeight);
  const tr = document.querySelector(".trust-row");
  const tb = document.querySelector(".trust-badges");
  return {
    ctaTop: px(c.top + scrollY), ctaBottom: px(c.bottom + scrollY),
    doc: px(document.documentElement.scrollHeight),
    subChars: sub.textContent.trim().length, subLines: Math.round(s.height / lh),
    trustRowVisible: tr ? tr.getBoundingClientRect().height > 0 : null,
    trustBadgesVisible: tb ? tb.getBoundingClientRect().height > 0 : null,
    trustBadgeRows: tb ? [...new Set([...tb.children].map(e => Math.round(e.getBoundingClientRect().top)))].length : null,
  };
};

const run = async () => {
  const browser = await chromium.launch({ executablePath: "/opt/pw-browsers/chromium-1194/chrome-linux/chrome" });
  const measure = async (width, css, subtitle) => {
    const ctx = await browser.newContext({
      viewport: { width, height: 780 }, deviceScaleFactor: 1, isMobile: true, hasTouch: true,
      locale: "fa-IR", extraHTTPHeaders: { "accept-language": "fa-IR,fa;q=0.9" }, colorScheme: "dark",
    });
    await ctx.addCookies([{ name: "theme", value: "dark", url: SITE }, { name: "locale", value: "fa", url: SITE }]);
    const page = await ctx.newPage();
    await page.goto(`${SITE}/`, { waitUntil: "networkidle", timeout: 45000 }).catch(() => {});
    await page.evaluate(() => document.fonts?.ready);
    if (subtitle != null) await page.evaluate((t) => { document.querySelector(".hero-copy .sub").textContent = t; }, subtitle);
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

  const out = { baseline: {}, combo5: {}, option6: {}, shorten: [] };
  for (const w of WIDTHS) {
    out.baseline[w] = await measure(w, "", null);
    out.combo5[w] = await measure(w, COMBO5, null);
    out.option6[w] = await measure(w, OPTION6, null);
  }

  // --- item 4: shorten the subtitle a word at a time until combination 5 clears at 360 ---------
  const words = REPO_DEFAULT.split(" ");
  for (let drop = 0; drop <= words.length - 4; drop++) {
    const text = words.slice(0, words.length - drop).join(" ");
    const r = await measure(360, COMBO5, text);
    out.shorten.push({ wordsDropped: drop, chars: text.length, subLines: r.subLines,
                       ctaBottom: r.ctaBottom, clears: r.ctaBottom <= TARGET, text });
    if (r.ctaBottom <= TARGET) break;
  }
  await browser.close();
  await writeFile(`${OUT}/g3-fold.json`, JSON.stringify(out, null, 2));

  const OFFSET = 88.7; // the addendum's own measurement: production CTA top 964 vs repo 875.3
  console.log(`target: CTA bottom <= ${TARGET}  (fold ${FOLD} - ${MARGIN})\n`);
  console.log("=== measured on the REPO baseline ===");
  console.log("scenario           width   CTA top   CTA bottom   clears?   trust-row   trust-badges");
  for (const [name, set] of [["baseline", out.baseline], ["combination 5", out.combo5], ["option 6", out.option6]]) {
    for (const w of WIDTHS) {
      const r = set[w];
      console.log(`${name.padEnd(18)}${String(w).padStart(5)}   ${String(r.ctaTop).padStart(7)}   ${String(r.ctaBottom).padStart(10)}   ${(r.ctaBottom <= TARGET ? "YES" : "no").padStart(7)}   ${String(r.trustRowVisible).padStart(9)}   ${String(r.trustBadgesVisible).padStart(12)}`);
    }
  }
  console.log(`\n=== restated on PRODUCTION, using the addendum's own +${OFFSET}px CTA offset ===`);
  console.log("scenario           width   CTA top   CTA bottom   clears 702?");
  for (const [name, set] of [["combination 5", out.combo5], ["option 6", out.option6]]) {
    for (const w of WIDTHS) {
      const t = Math.round((set[w].ctaTop + OFFSET) * 10) / 10, b = Math.round((set[w].ctaBottom + OFFSET) * 10) / 10;
      console.log(`${name.padEnd(18)}${String(w).padStart(5)}   ${String(t).padStart(7)}   ${String(b).padStart(10)}   ${(b <= TARGET ? "YES" : "no").padStart(11)}`);
    }
  }
  console.log("\n=== item 4: shortening the subtitle until combination 5 clears at 360 ===");
  console.log("words dropped  chars  sub lines  CTA bottom  clears 702?");
  for (const s of out.shorten)
    console.log(`${String(s.wordsDropped).padStart(13)}  ${String(s.chars).padStart(5)}  ${String(s.subLines).padStart(9)}  ${String(s.ctaBottom).padStart(10)}  ${s.clears ? "YES" : "no"}`);
  const win = out.shorten.find(s => s.clears);
  if (win) console.log(`\n  smallest clearing length: ${win.chars} characters (${win.subLines} lines at 360px)\n  «${win.text}»`);
  else console.log("\n  never clears at 360 by shortening the subtitle alone");
};
run();
