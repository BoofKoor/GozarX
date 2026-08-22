// Verification pass for the two places where "dominant colour of the rect" is a weak estimator:
// the hero headline (its ground is itself a radial gradient) and the CTA (its own fill is a
// gradient). Both are read from ACTUAL PIXELS at named points instead.

import { chromium } from "playwright";
import { writeFile } from "node:fs/promises";
import { PNG } from "pngjs";

const SITE = "http://127.0.0.1:3100";
const OUT = "/tmp/claude-0/-home-user-GozarX/c019534b-02b6-53f9-aaf3-f0202784f44e/scratchpad/out";
const lin = (c) => { c /= 255; return c <= 0.04045 ? c / 12.92 : Math.pow((c + 0.055) / 1.055, 2.4); };
const L = ([r, g, b]) => 0.2126 * lin(r) + 0.7152 * lin(g) + 0.0722 * lin(b);
const ratio = (a, b) => { const l1 = L(a), l2 = L(b); const [hi, lo] = l1 > l2 ? [l1, l2] : [l2, l1]; return Math.round(((hi + 0.05) / (lo + 0.05)) * 100) / 100; };
const hex = ([r, g, b]) => "#" + [r, g, b].map((v) => Math.round(v).toString(16).padStart(2, "0")).join("");
const mix = (a, b, t) => a.map((v, i) => v + (b[i] - v) * t);

const pixAt = (buf, x, y) => {
  const png = PNG.sync.read(buf);
  const i = (png.width * y + x) * 4;
  return [png.data[i], png.data[i + 1], png.data[i + 2]];
};

const run = async () => {
  const browser = await chromium.launch({ executablePath: "/opt/pw-browsers/chromium-1194/chrome-linux/chrome" });
  const res = {};
  for (const theme of ["dark", "light"]) {
    const ctx = await browser.newContext({
      viewport: { width: 390, height: 780 }, deviceScaleFactor: 1, isMobile: true, hasTouch: true,
      locale: "fa-IR", extraHTTPHeaders: { "accept-language": "fa-IR,fa;q=0.9" }, colorScheme: theme,
    });
    await ctx.addCookies([{ name: "theme", value: theme, url: SITE }, { name: "locale", value: "fa", url: SITE }]);
    const page = await ctx.newPage();
    await page.goto(`${SITE}/`, { waitUntil: "networkidle", timeout: 45000 }).catch(() => {});
    await page.evaluate(() => document.fonts?.ready);
    await page.addStyleTag({ content: "*{animation:none !important;transition:none !important}" });
    await page.waitForTimeout(400);

    // Hide the headline text only, then read the ground under where the glyphs were, at 5 points
    // along the gradient span's own line box.
    const geo = await page.evaluate(() => {
      const g = document.querySelector(".hero-copy h1 .grad");
      const r = g.getBoundingClientRect();
      return { x: r.left, y: r.top, w: r.width, h: r.height, cy: r.top + r.height / 2,
               image: getComputedStyle(g).backgroundImage };
    });
    await page.evaluate(() => {
      const g = document.querySelector(".hero-copy h1");
      g.style.setProperty("visibility", "hidden", "important");
    });
    await page.waitForTimeout(120);
    const shotBg = await page.screenshot({ clip: { x: 0, y: 0, width: 390, height: 400 } });
    const pts = [0.05, 0.3, 0.5, 0.7, 0.95].map((f) => {
      const x = Math.round(geo.x + geo.w * f), y = Math.round(geo.cy);
      return { f, x, y, rgb: pixAt(shotBg, x, y) };
    });
    await page.evaluate(() => document.querySelector(".hero-copy h1").style.removeProperty("visibility"));

    const stops = [...geo.image.matchAll(/rgb\((\d+),\s*(\d+),\s*(\d+)\)/g)].map((m) => [+m[1], +m[2], +m[3]]);
    // In an RTL line box the visual LEFT edge is the gradient's 120deg START only because the span
    // itself is not mirrored — record both the geometric fraction and the colour there.
    const grad = pts.map((p) => {
      const c = mix(stops[0], stops[1], p.f);
      return { atFractionOfSpan: p.f, glyphColor: hex(c), groundHere: hex(p.rgb), ratio: ratio(c, p.rgb) };
    });

    // CTA: its fill is a gradient too — read the actual button pixels beside the label.
    const ctaGeo = await page.evaluate(() => {
      const b = document.querySelector(".cta");
      b.scrollIntoView({ block: "center" });
      const r = b.getBoundingClientRect();
      return { x: r.left, y: r.top, w: r.width, h: r.height, color: getComputedStyle(b).color };
    });
    await page.waitForTimeout(150);
    const ctaShot = await page.screenshot({ clip: { x: Math.round(ctaGeo.x), y: Math.round(ctaGeo.y), width: Math.round(ctaGeo.w), height: Math.round(ctaGeo.h) } });
    const ctaFg = ctaGeo.color.match(/[\d.]+/g).slice(0, 3).map(Number);
    const ctaPts = [0.03, 0.25, 0.5, 0.75, 0.97].map((f) => {
      const x = Math.min(Math.round(ctaGeo.w * f), Math.round(ctaGeo.w) - 1);
      const y = 3; // top strip: inside the button, above the text baseline
      const rgb = pixAt(ctaShot, x, y);
      return { f, ground: hex(rgb), ratio: ratio(ctaFg, rgb) };
    });

    res[theme] = { gradientStops: stops.map(hex), gradientSamples: grad, ctaLabel: hex(ctaFg), ctaSamples: ctaPts };
    await ctx.close();
  }
  await browser.close();
  await writeFile(`${OUT}/verify-contrast.json`, JSON.stringify(res, null, 2));
  for (const t of ["dark", "light"]) {
    console.log(`\n===== ${t} =====  gradient stops ${res[t].gradientStops.join(" → ")}`);
    console.log("  hero headline, ground read from actual pixels with the text hidden:");
    for (const g of res[t].gradientSamples)
      console.log(`    at ${String(g.atFractionOfSpan).padStart(4)} of span: glyph ${g.glyphColor} on ground ${g.groundHere} → ${String(g.ratio).padStart(5)}  ${g.ratio >= 3 ? "" : "**FAIL (needs 3:1, large text)**"}`);
    console.log(`  CTA label ${res[t].ctaLabel} on its own gradient fill:`);
    for (const c of res[t].ctaSamples)
      console.log(`    at ${String(c.f).padStart(4)}: ground ${c.ground} → ${String(c.ratio).padStart(5)}  ${c.ratio >= 4.5 ? "" : "**below 4.5**"}`);
  }
};
run();
