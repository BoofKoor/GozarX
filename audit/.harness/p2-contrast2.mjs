// Contrast, corrected. Two fixes over the first pass:
//  1. The background is the DOMINANT colour of the element's own rendered rect — glyph coverage is
//     well under half, so this needs no mutation and therefore cannot destroy a button's own
//     gradient (which is what made .cta read white-on-white and .grad read black).
//  2. A background-clip:text headline has no single colour. Its gradient is evaluated analytically
//     at both stops and the midpoint, each against the pixel-sampled ground behind the glyphs.

import { chromium } from "playwright";
import { writeFile } from "node:fs/promises";
import { PNG } from "pngjs";

const SITE = "http://127.0.0.1:3100";
const OUT = "/tmp/claude-0/-home-user-GozarX/c019534b-02b6-53f9-aaf3-f0202784f44e/scratchpad/out";
const lin = (c) => { c /= 255; return c <= 0.04045 ? c / 12.92 : Math.pow((c + 0.055) / 1.055, 2.4); };
const L = ([r, g, b]) => 0.2126 * lin(r) + 0.7152 * lin(g) + 0.0722 * lin(b);
const ratio = (a, b) => { const l1 = L(a), l2 = L(b); const [hi, lo] = l1 > l2 ? [l1, l2] : [l2, l1]; return Math.round(((hi + 0.05) / (lo + 0.05)) * 100) / 100; };
const hex = ([r, g, b]) => "#" + [r, g, b].map((v) => Math.round(v).toString(16).padStart(2, "0")).join("");
const parseHex = (h) => [1, 3, 5].map((i) => parseInt(h.slice(i, i + 2), 16));
const mix = (a, b, t) => a.map((v, i) => v + (b[i] - v) * t);

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

const TARGETS = [
  ["G3 antibot line", ".antibot"],
  ["G3 livepill «۲۹ لوکیشن»", ".livepill"],
  ["G3 widget sub «یک لوکیشن…»", ".w-sub"],
  ["G2 reward badge figure (.mvamt b)", ".mvamt b"],
  ["G2 reward badge unit (.mvamt i)", ".mvamt i"],
  ["G2 mission title (.mvbd h3)", ".mvbd h3"],
  ["CTA label (.cta)", ".cta"],
  ["footer CTA (.ft-cta-btn)", ".ft-cta-btn"],
  ["appcard rec badge (.app-rec)", ".appcard .app-rec"],
  ["loc-rec «popular» badge", ".loc-rec"],
  ["faint token sample (.hint/.faint)", ".antibot .ic"],
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
    await page.addStyleTag({ content: "*{animation:none !important;transition:none !important}" });
    await page.waitForTimeout(300);

    const rows = [];
    for (const [name, q] of TARGETS) {
      const info = await page.evaluate((sel) => {
        const el = document.querySelector(sel);
        if (!el) return null;
        el.setAttribute("data-probe", "1");
        el.scrollIntoView({ block: "center" });
        const r = el.getBoundingClientRect();
        if (r.width < 3 || r.height < 3) return null;
        const c = getComputedStyle(el);
        return {
          text: (el.textContent || "").trim().slice(0, 40),
          color: c.color, fontSize: c.fontSize, fontWeight: c.fontWeight,
          clip: { x: Math.max(0, r.left), y: Math.max(0, r.top), width: Math.min(r.width, innerWidth - r.left), height: r.height },
        };
      }, q);
      if (!info) { rows.push({ name, missing: true }); continue; }
      const shot = await page.screenshot({ clip: info.clip });
      const bg = dominant(shot);
      await page.evaluate(() => document.querySelector('[data-probe="1"]')?.removeAttribute("data-probe"));
      const m = info.color.match(/[\d.]+/g);
      const fg = m.slice(0, 3).map(Number);
      const alpha = m.length > 3 ? Number(m[3]) : 1;
      const eff = alpha < 1 ? mix(bg.rgb, fg, alpha) : fg;
      const fs = parseFloat(info.fontSize);
      const large = fs >= 24 || (fs >= 18.66 && Number(info.fontWeight) >= 700);
      rows.push({
        name, text: info.text, fontSize: info.fontSize, fontWeight: info.fontWeight,
        color: hex(eff), effectiveBg: hex(bg.rgb), bgShare: Math.round(bg.share * 100),
        ratio: ratio(eff, bg.rgb), threshold: large ? 3 : 4.5,
        pass: ratio(eff, bg.rgb) >= (large ? 3 : 4.5), large,
      });
    }

    // --- the gradient headline, analytically -------------------------------------------------
    const gradInfo = await page.evaluate(() => {
      const g = document.querySelector(".hero-copy h1 .grad");
      const h1 = document.querySelector(".hero-copy h1");
      if (!g) return null;
      h1.scrollIntoView({ block: "center" });
      const r = g.getBoundingClientRect();
      return {
        image: getComputedStyle(g).backgroundImage,
        text: g.textContent,
        clip: { x: Math.max(0, r.left), y: Math.max(0, r.top), width: Math.min(r.width, innerWidth - r.left), height: r.height },
        fontSize: getComputedStyle(g).fontSize, fontWeight: getComputedStyle(g).fontWeight,
      };
    });
    if (gradInfo) {
      // Background behind the glyphs: sample the h1's own row, which is mostly hero ground.
      const shot = await page.screenshot({ clip: gradInfo.clip });
      const bg = dominant(shot);
      const stops = [...gradInfo.image.matchAll(/rgb\((\d+),\s*(\d+),\s*(\d+)\)/g)].map((m) => [ +m[1], +m[2], +m[3] ]);
      const samples = {};
      if (stops.length >= 2) {
        for (const t of [0, 0.25, 0.5, 0.75, 1]) {
          const c = mix(stops[0], stops[stops.length - 1], t);
          samples[`t=${t}`] = { color: hex(c), ratio: ratio(c, bg.rgb) };
        }
      }
      const fs = parseFloat(gradInfo.fontSize);
      const large = fs >= 24 || (fs >= 18.66 && Number(gradInfo.fontWeight) >= 700);
      results[`${theme}__gradient`] = {
        text: gradInfo.text, image: gradInfo.image, effectiveBg: hex(bg.rgb), bgShare: Math.round(bg.share * 100),
        fontSize: gradInfo.fontSize, large, threshold: large ? 3 : 4.5, samples,
        worst: Object.entries(samples).reduce((a, b) => (a[1].ratio <= b[1].ratio ? a : b)),
      };
    }
    results[theme] = rows;
    await ctx.close();
  }
  await browser.close();
  await writeFile(`${OUT}/contrast2.json`, JSON.stringify(results, null, 2));
  for (const theme of ["dark", "light"]) {
    console.log(`\n===== ${theme.toUpperCase()} =====`);
    for (const r of results[theme]) {
      if (r.missing) { console.log(`  ${r.name.padEnd(36)} MISSING`); continue; }
      console.log(`  ${r.name.slice(0,35).padEnd(36)} fg=${r.color} bg=${r.effectiveBg}(${r.bgShare}%) ratio=${String(r.ratio).padStart(6)} need=${r.threshold} ${r.pass ? "PASS" : "**FAIL**"}  «${r.text}»`);
    }
    const g = results[`${theme}__gradient`];
    if (g) {
      console.log(`  -- gradient headline «${g.text}» over ${g.effectiveBg} (${g.bgShare}% of rect), need ${g.threshold}`);
      for (const [k, v] of Object.entries(g.samples)) console.log(`      ${k}: ${v.color} ratio=${v.ratio} ${v.ratio >= g.threshold ? "" : "**FAIL**"}`);
    }
  }
};
run();
