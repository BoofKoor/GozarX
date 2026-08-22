// G — contrast measured against the EFFECTIVE background: for each text run we screenshot its own
// rect twice, once as rendered and once with that element's text hidden. The dominant colour of the
// hidden shot IS the background actually behind the glyphs (after every gradient, ::before wash,
// radial overlay and translucency), so the ratio is not a token-vs-token guess.

import { chromium } from "playwright";
import { writeFile } from "node:fs/promises";
import { PNG } from "pngjs";

const SITE = "http://127.0.0.1:3100";
const OUT = "/tmp/claude-0/-home-user-GozarX/c019534b-02b6-53f9-aaf3-f0202784f44e/scratchpad/out";

const lin = (c) => { c /= 255; return c <= 0.04045 ? c / 12.92 : Math.pow((c + 0.055) / 1.055, 2.4); };
const L = ([r, g, b]) => 0.2126 * lin(r) + 0.7152 * lin(g) + 0.0722 * lin(b);
const ratio = (a, b) => { const l1 = L(a), l2 = L(b); const [hi, lo] = l1 > l2 ? [l1, l2] : [l2, l1]; return (hi + 0.05) / (lo + 0.05); };
const hex = ([r, g, b]) => "#" + [r, g, b].map((v) => v.toString(16).padStart(2, "0")).join("");

function dominant(buf) {
  const png = PNG.sync.read(buf);
  const counts = new Map();
  for (let i = 0; i < png.data.length; i += 4) {
    if (png.data[i + 3] < 250) continue;
    const k = `${png.data[i]},${png.data[i + 1]},${png.data[i + 2]}`;
    counts.set(k, (counts.get(k) || 0) + 1);
  }
  let best = null, bn = -1;
  for (const [k, n] of counts) if (n > bn) { bn = n; best = k; }
  return { rgb: best.split(",").map(Number), share: bn / (png.width * png.height) };
}
// The darkest / lightest actual glyph pixel in the rendered shot — a gradient-filled headline has no
// single "colour", so its worst point is what has to clear AA.
function extremes(buf, bg) {
  const png = PNG.sync.read(buf);
  let worst = null, worstR = Infinity;
  for (let i = 0; i < png.data.length; i += 4) {
    if (png.data[i + 3] < 250) continue;
    const p = [png.data[i], png.data[i + 1], png.data[i + 2]];
    // skip pixels that ARE the background
    if (Math.abs(p[0] - bg[0]) + Math.abs(p[1] - bg[1]) + Math.abs(p[2] - bg[2]) < 12) continue;
    const r = ratio(p, bg);
    if (r < worstR) { worstR = r; worst = p; }
  }
  return worst ? { rgb: worst, ratio: Math.round(worstR * 100) / 100 } : null;
}

const TARGETS = [
  ["G3 «با یک بررسی نامرئی…» (antibot)", ".antibot"],
  ["G3 «۲۹ لوکیشن» (livepill)", ".livepill"],
  ["G3 picker sub «یک لوکیشن…» (w-sub)", ".w-sub"],
  ["G3 pick-label count (.pick-label .c)", ".pick-label .c"],
  ["section subtitle (.sec-sub)", ".sec-sub"],
  ["section title (.sec-title)", ".sec-title"],
  ["hero subtitle (.hero-copy .sub)", ".hero-copy .sub"],
  ["G2 reward badge «+N MB» (.mvamt b)", ".mvamt b"],
  ["G2 reward badge unit (.mvamt i)", ".mvamt i"],
  ["G2 mission card title (.mvbd h3)", ".mvbd h3"],
  ["G2 mission card body (.mvbd p)", ".mvbd p"],
  ["stat figure (.statband .n)", ".statband .n"],
  ["stat label (.statband .l)", ".statband .l"],
  ["step body (.step p)", ".step p"],
  ["article chip (.art-chips .chip)", ".art-chips .chip"],
  ["footer col link (.ft-col a)", ".ft-col a"],
  ["footer keyword link (.ft-more a)", ".ft-more a"],
  ["footer trust line (.ft-brand p)", ".ft-brand p"],
  ["footer bottom (.ft-bottom)", ".ft-bottom"],
  ["eyebrow (.eyebrow)", ".eyebrow"],
  ["trust badge (.tb)", ".tb"],
  ["hero pill (.trust-row .pill)", ".trust-row .pill"],
  ["loc caption (.loccap)", ".loccap"],
  ["appcard subtitle (.appcard .ap)", ".appcard .ap"],
  ["appcard rec badge (.app-rec)", ".appcard .app-rec"],
  ["accordion head (.acc-head)", ".acc-head"],
  ["loc-card name (.loc-card .nm)", ".loc-card .nm"],
  ["F2 hero gradient headline (.grad)", ".hero-copy h1 .grad"],
  ["hero h1 plain part (h1)", ".hero-copy h1"],
  ["CTA label (.cta)", ".cta"],
  ["footer CTA (.ft-cta-btn)", ".ft-cta-btn"],
  ["link-more (.link-more)", ".link-more"],
  ["loccta (.loccta)", ".loccta"],
];

const run = async () => {
  const browser = await chromium.launch({ executablePath: "/opt/pw-browsers/chromium-1194/chrome-linux/chrome" });
  const results = {};
  for (const theme of ["dark", "light"]) {
    const ctx = await browser.newContext({
      viewport: { width: 390, height: 780 }, deviceScaleFactor: 2, isMobile: true, hasTouch: true,
      locale: "fa-IR", extraHTTPHeaders: { "accept-language": "fa-IR,fa;q=0.9" }, colorScheme: theme,
    });
    await ctx.addCookies([{ name: "theme", value: theme, url: SITE }, { name: "locale", value: "fa", url: SITE }]);
    const page = await ctx.newPage();
    await page.goto(`${SITE}/`, { waitUntil: "networkidle", timeout: 45000 }).catch(() => {});
    await page.evaluate(async () => {
      for (let y = 0; y < document.body.scrollHeight; y += 600) { scrollTo(0, y); await new Promise(r => setTimeout(r, 40)); }
      scrollTo(0, 0); await new Promise(r => setTimeout(r, 250));
    });
    await page.evaluate(() => document.fonts?.ready);
    // freeze animations so the sampled frame is stable
    await page.addStyleTag({ content: "*{animation:none !important;transition:none !important}" });
    await page.waitForTimeout(300);

    const rows = [];
    for (const [name, q] of TARGETS) {
      const info = await page.evaluate((sel) => {
        const el = document.querySelector(sel);
        if (!el) return null;
        const r = el.getBoundingClientRect();
        if (r.width < 2 || r.height < 2) return null;
        el.setAttribute("data-probe", "1");
        return {
          color: getComputedStyle(el).color,
          fontSize: getComputedStyle(el).fontSize,
          fontWeight: getComputedStyle(el).fontWeight,
          box: { x: r.left + scrollX, y: r.top + scrollY, w: r.width, h: r.height },
        };
      }, q);
      if (!info) { rows.push({ name, sel: q, missing: true }); continue; }
      // scroll it into view, then clip-shoot
      const clip = await page.evaluate(() => {
        const el = document.querySelector('[data-probe="1"]');
        el.scrollIntoView({ block: "center" });
        const r = el.getBoundingClientRect();
        return { x: Math.max(0, r.left), y: Math.max(0, r.top), width: Math.max(2, Math.min(r.width, innerWidth - r.left)), height: Math.max(2, r.height) };
      });
      const shotOn = await page.screenshot({ clip });
      await page.evaluate(() => {
        const el = document.querySelector('[data-probe="1"]');
        el.dataset.prevVis = el.style.color;
        el.style.setProperty("color", "transparent", "important");
        el.querySelectorAll("*").forEach((c) => c.style.setProperty("color", "transparent", "important"));
        el.querySelectorAll("*").forEach((c) => { if (c.tagName === "svg" || c.tagName === "IMG") c.style.visibility = "hidden"; });
        // a gradient-clipped headline paints via background-clip:text — kill that too
        el.style.setProperty("background-image", "none", "important");
        el.style.setProperty("-webkit-text-fill-color", "transparent", "important");
      });
      const shotOff = await page.screenshot({ clip });
      const bg = dominant(shotOff);
      const worst = extremes(shotOn, bg.rgb);
      await page.evaluate(() => {
        const el = document.querySelector('[data-probe="1"]');
        el.removeAttribute("style");
        el.querySelectorAll("*").forEach((c) => c.removeAttribute("style"));
        el.removeAttribute("data-probe");
      });
      const fg = info.color.match(/[\d.]+/g).slice(0, 3).map(Number);
      rows.push({
        name, sel: q, fontSize: info.fontSize, fontWeight: info.fontWeight,
        computedColor: hex(fg),
        effectiveBg: hex(bg.rgb), bgShare: Math.round(bg.share * 100),
        ratioComputed: Math.round(ratio(fg, bg.rgb) * 100) / 100,
        worstPixel: worst ? hex(worst.rgb) : null,
        ratioWorstPixel: worst ? worst.ratio : null,
        passAA: ratio(fg, bg.rgb) >= 4.5,
        largeText: parseFloat(info.fontSize) >= 24 || (parseFloat(info.fontSize) >= 18.66 && Number(info.fontWeight) >= 700),
      });
    }
    results[theme] = rows;
    await ctx.close();
  }
  await browser.close();
  await writeFile(`${OUT}/contrast.json`, JSON.stringify(results, null, 2));
  for (const theme of ["dark", "light"]) {
    console.log(`\n===== ${theme.toUpperCase()} =====`);
    console.log("target".padEnd(40) + "fg".padEnd(10) + "bg".padEnd(10) + "ratio".padStart(7) + "  worstPx".padStart(10) + "  AA");
    for (const r of results[theme]) {
      if (r.missing) { console.log(`${r.name.padEnd(40)}MISSING`); continue; }
      const aa = r.largeText ? (r.ratioComputed >= 3 ? "ok(lg)" : "FAIL(lg)") : (r.passAA ? "ok" : "FAIL");
      console.log(`${r.name.slice(0,39).padEnd(40)}${r.computedColor.padEnd(10)}${r.effectiveBg.padEnd(10)}${String(r.ratioComputed).padStart(7)}  ${String(r.ratioWorstPixel).padStart(8)}  ${aa}`);
    }
  }
};
run();
