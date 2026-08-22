// Gate 2 · item 2 — the CTA's real geometry, and a reconciliation of the addendum's 7,995 / y=964
// against the Gate-1 baseline of 7,908 / y=875. Both gaps are ~88px, so this also tests the two
// things that could add ~88px at the top of the document.

import { chromium } from "playwright";
import { writeFile } from "node:fs/promises";

const SITE = "http://127.0.0.1:3100";
const OUT = "/tmp/claude-0/-home-user-GozarX/c019534b-02b6-53f9-aaf3-f0202784f44e/scratchpad/out";
const WIDTHS = [360, 390, 393, 412];

const geom = () => {
  const px = (v) => Math.round(v * 10) / 10;
  const abs = (el) => { const r = el.getBoundingClientRect(); return { top: px(r.top + scrollY), bottom: px(r.bottom + scrollY), h: px(r.height), w: px(r.width) }; };
  const cta = document.querySelector(".cta");
  const widget = document.querySelector("#hero-widget .widget");
  const hero = document.querySelector(".hero");
  const banner = document.querySelector(".lang-banner");
  const hd = document.querySelector("header.hd");
  const h1 = document.querySelector(".hero-copy h1");
  const sub = document.querySelector(".hero-copy .sub");
  const trust = document.querySelector(".trust-row");
  const picker = document.querySelector(".loc-scroll > .loc-grid");
  const pickLabel = document.querySelector(".pick-label");
  const whead = document.querySelector(".w-head");
  return {
    docHeight: px(document.documentElement.scrollHeight),
    viewport: { w: innerWidth, h: innerHeight },
    langBannerPresent: !!banner,
    langBannerHeight: banner ? abs(banner).h : 0,
    header: hd ? abs(hd) : null,
    hero: hero ? abs(hero) : null,
    h1: h1 ? abs(h1) : null,
    sub: sub ? abs(sub) : null,
    trustRow: trust ? abs(trust) : null,
    widget: widget ? { ...abs(widget), minBlockSize: getComputedStyle(widget).minHeight,
                       naturalContent: px(widget.scrollHeight) } : null,
    wHead: whead ? abs(whead) : null,
    pickLabel: pickLabel ? abs(pickLabel) : null,
    picker: picker ? { ...abs(picker), maxH: getComputedStyle(picker).maxHeight, scrollH: picker.scrollHeight } : null,
    cta: cta ? { ...abs(cta),
      marginTop: getComputedStyle(cta.parentElement).marginTop,
      paddingBlock: getComputedStyle(cta).paddingTop + "/" + getComputedStyle(cta).paddingBottom,
      fontSize: getComputedStyle(cta).fontSize, lineHeight: getComputedStyle(cta).lineHeight } : null,
  };
};

const run = async () => {
  const browser = await chromium.launch({ executablePath: "/opt/pw-browsers/chromium-1194/chrome-linux/chrome" });
  const out = { primary: {}, hypotheses: {} };

  // --- the Gate-1 conditions, at all four widths -----------------------------------------
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
    await page.waitForTimeout(350);
    out.primary[width] = await page.evaluate(geom);
    await ctx.close();
  }

  // --- what could add ~88px? ---------------------------------------------------------------
  const variants = {
    "dark, no cookies at all (banner may show)": { cookies: [], scheme: "dark", al: "fa-IR,fa;q=0.9" },
    "LIGHT theme": { cookies: [{ name: "theme", value: "light" }, { name: "locale", value: "fa" }], scheme: "light", al: "fa-IR,fa;q=0.9" },
    "en locale": { cookies: [{ name: "theme", value: "dark" }, { name: "locale", value: "en" }], scheme: "dark", al: "en-US,en;q=0.9" },
    "no scroll-settle (reveal not fired)": { cookies: [{ name: "theme", value: "dark" }, { name: "locale", value: "fa" }], scheme: "dark", al: "fa-IR,fa;q=0.9", noSettle: true },
    "desktop UA (isMobile false)": { cookies: [{ name: "theme", value: "dark" }, { name: "locale", value: "fa" }], scheme: "dark", al: "fa-IR,fa;q=0.9", desktop: true },
  };
  for (const [name, v] of Object.entries(variants)) {
    const ctx = await browser.newContext({
      viewport: { width: 390, height: 780 }, deviceScaleFactor: 2,
      isMobile: !v.desktop, hasTouch: !v.desktop,
      locale: "fa-IR", extraHTTPHeaders: { "accept-language": v.al }, colorScheme: v.scheme,
    });
    if (v.cookies.length) await ctx.addCookies(v.cookies.map((c) => ({ ...c, url: SITE })));
    const page = await ctx.newPage();
    await page.goto(`${SITE}/`, { waitUntil: "networkidle", timeout: 45000 }).catch(() => {});
    if (!v.noSettle) {
      await page.evaluate(async () => {
        for (let y = 0; y < document.body.scrollHeight; y += 600) { scrollTo(0, y); await new Promise(r => setTimeout(r, 40)); }
        scrollTo(0, 0); await new Promise(r => setTimeout(r, 200));
      });
    }
    await page.evaluate(() => document.fonts?.ready);
    await page.waitForTimeout(350);
    const g = await page.evaluate(geom);
    out.hypotheses[name] = { docHeight: g.docHeight, ctaTop: g.cta?.top, ctaBottom: g.cta?.bottom,
                             langBanner: g.langBannerHeight, headerH: g.header?.h };
    await ctx.close();
  }
  await browser.close();
  await writeFile(`${OUT}/g2-cta.json`, JSON.stringify(out, null, 2));

  console.log("=== CTA GEOMETRY (Gate-1 conditions: dark, fa, mobile emulation, settled) ===");
  console.log("width  docHeight   CTA top  CTA height  CTA bottom   widget minH  widget natural");
  for (const w of WIDTHS) {
    const g = out.primary[w];
    console.log(`${String(w).padStart(5)}  ${String(g.docHeight).padStart(9)}  ${String(g.cta.top).padStart(8)}  ${String(g.cta.h).padStart(10)}  ${String(g.cta.bottom).padStart(10)}   ${String(g.widget.minBlockSize).padStart(11)}  ${String(g.widget.naturalContent).padStart(14)}`);
  }
  console.log("\n=== the stack above the CTA @390 ===");
  const g = out.primary[390];
  for (const [k, v] of Object.entries({ header: g.header, hero: g.hero, h1: g.h1, sub: g.sub,
      trustRow: g.trustRow, widget: g.widget, wHead: g.wHead, pickLabel: g.pickLabel, picker: g.picker, cta: g.cta })) {
    if (v) console.log(`  ${k.padEnd(11)} top=${String(v.top).padStart(7)}  h=${String(v.h).padStart(7)}  bottom=${String(v.bottom).padStart(7)}`);
  }
  console.log("\n=== reconciliation: what changes the baseline? (all @390) ===");
  console.log(`  ${"Gate-1 baseline".padEnd(42)} doc=${out.primary[390].docHeight}  ctaTop=${out.primary[390].cta.top}  ctaBottom=${out.primary[390].cta.bottom}`);
  for (const [k, v] of Object.entries(out.hypotheses))
    console.log(`  ${k.padEnd(42)} doc=${v.docHeight}  ctaTop=${v.ctaTop}  ctaBottom=${v.ctaBottom}  banner=${v.langBanner}  hdr=${v.headerH}`);
};
run();
