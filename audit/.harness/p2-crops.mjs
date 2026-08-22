// Targeted crops + the two measurements that need real pixels: the third-party app tile's
// luminance against its card (G4) and the stats-tile status dot's position on the tile's rounded
// corner (H7). Also a scrolled shot of the sticky header with content under it (E1).

import { chromium } from "playwright";
import { writeFile } from "node:fs/promises";
import { PNG } from "pngjs";

const SITE = "http://127.0.0.1:3100";
const OUT = "/tmp/claude-0/-home-user-GozarX/c019534b-02b6-53f9-aaf3-f0202784f44e/scratchpad/out";
const lin = (c) => { c /= 255; return c <= 0.04045 ? c / 12.92 : Math.pow((c + 0.055) / 1.055, 2.4); };
const L = ([r, g, b]) => 0.2126 * lin(r) + 0.7152 * lin(g) + 0.0722 * lin(b);
const hex = ([r, g, b]) => "#" + [r, g, b].map((v) => Math.round(v).toString(16).padStart(2, "0")).join("");

function meanLuma(buf) {
  const png = PNG.sync.read(buf);
  let sum = 0, n = 0, rs = 0, gs = 0, bs = 0;
  for (let i = 0; i < png.data.length; i += 4) {
    if (png.data[i + 3] < 250) continue;
    sum += L([png.data[i], png.data[i + 1], png.data[i + 2]]);
    rs += png.data[i]; gs += png.data[i + 1]; bs += png.data[i + 2]; n++;
  }
  return { meanLuma: Math.round((sum / n) * 1000) / 1000, meanColor: hex([rs / n, gs / n, bs / n]), px: n };
}

const CROPS = [
  ["hero-headline", ".hero-copy h1", 14],
  ["trust-row-clip", ".trust-row", 8],
  ["locations-card", ".loccard", 6],
  ["flagstrip", ".flagstrip", 6],
  ["step-card", ".step", 6],
  ["mission-rows", ".mvlist", 6],
  ["appcards", ".approw", 6],
  ["statband", ".statband", 8],
  ["trust-badges", ".trust-badges", 8],
  ["article-chips", ".art-chips", 6],
  ["footer-keywords", ".ft-more", 6],
  ["footer-grid", ".ft-grid", 6],
  ["picker-grid", ".loc-scroll", 6],
];

const run = async () => {
  const browser = await chromium.launch({ executablePath: "/opt/pw-browsers/chromium-1194/chrome-linux/chrome" });
  const ctx = await browser.newContext({
    viewport: { width: 390, height: 780 }, deviceScaleFactor: 2, isMobile: true, hasTouch: true,
    locale: "fa-IR", extraHTTPHeaders: { "accept-language": "fa-IR,fa;q=0.9" }, colorScheme: "dark",
  });
  await ctx.addCookies([{ name: "theme", value: "dark", url: SITE }, { name: "locale", value: "fa", url: SITE }]);
  const page = await ctx.newPage();
  await page.goto(`${SITE}/`, { waitUntil: "networkidle", timeout: 45000 }).catch(() => {});
  await page.evaluate(async () => {
    for (let y = 0; y < document.body.scrollHeight; y += 600) { scrollTo(0, y); await new Promise(r => setTimeout(r, 40)); }
    scrollTo(0, 0); await new Promise(r => setTimeout(r, 250));
  });
  await page.evaluate(() => document.fonts?.ready);
  await page.addStyleTag({ content: "*{animation:none !important;transition:none !important}" });
  await page.waitForTimeout(400);

  for (const [name, sel, pad] of CROPS) {
    const el = page.locator(sel).first();
    if (!(await el.count())) { console.log("MISSING", name); continue; }
    await el.scrollIntoViewIfNeeded();
    await page.waitForTimeout(150);
    const box = await el.boundingBox();
    if (!box) continue;
    await page.screenshot({
      path: `${OUT}/crop-${name}.png`,
      clip: { x: Math.max(0, box.x - pad), y: Math.max(0, box.y - pad),
              width: Math.min(390 - Math.max(0, box.x - pad), box.width + pad * 2), height: box.height + pad * 2 },
    });
  }

  // E1: sticky header with content passing under it
  await page.evaluate(() => scrollTo(0, 1500));
  await page.waitForTimeout(300);
  await page.screenshot({ path: `${OUT}/crop-header-scrolled.png`, clip: { x: 0, y: 0, width: 390, height: 150 } });
  await page.evaluate(() => scrollTo(0, 0));

  const out = {};

  // G4: each app tile's own luminance vs its card's surface
  out.appTiles = [];
  const n = await page.locator(".appcard").count();
  for (let i = 0; i < n; i++) {
    const card = page.locator(".appcard").nth(i);
    await card.scrollIntoViewIfNeeded();
    await page.waitForTimeout(120);
    const info = await card.evaluate((el) => {
      const img = el.querySelector(".big-ico");
      const r = img.getBoundingClientRect(), cr = el.getBoundingClientRect();
      const c = getComputedStyle(img);
      return {
        name: el.querySelector(".an")?.textContent?.trim(),
        src: img.getAttribute("src"), natural: `${img.naturalWidth}x${img.naturalHeight}`,
        rendered: `${Math.round(r.width)}x${Math.round(r.height)}`,
        objectFit: c.objectFit, filter: c.filter, background: c.backgroundColor, mixBlendMode: c.mixBlendMode,
        boxShadow: c.boxShadow.slice(0, 60),
        imgClip: { x: r.left, y: r.top, w: r.width, h: r.height },
        cardClip: { x: cr.left + cr.width * 0.55, y: cr.top + 6, w: 40, h: 20 },
      };
    });
    const imgShot = await page.screenshot({ clip: { x: info.imgClip.x, y: info.imgClip.y, width: info.imgClip.w, height: info.imgClip.h } });
    const cardShot = await page.screenshot({ clip: { x: info.cardClip.x, y: info.cardClip.y, width: info.cardClip.w, height: info.cardClip.h } });
    out.appTiles.push({ ...info, imgClip: undefined, cardClip: undefined, tile: meanLuma(imgShot), cardSurface: meanLuma(cardShot) });
  }
  // brightest title on the same band, for comparison
  const titleShot = await (async () => {
    const t = page.locator(".appcard .an").first();
    await t.scrollIntoViewIfNeeded();
    const b = await t.boundingBox();
    return page.screenshot({ clip: { x: b.x, y: b.y, width: b.width, height: b.height } });
  })();
  out.appTitleLuma = meanLuma(titleShot);

  // H7: the stats-tile status dot vs its OWN tile
  out.statDot = await page.evaluate(() => {
    const dot = document.querySelector(".statband .onb");
    if (!dot) return null;
    const tile = dot.closest(".tile");
    const d = dot.getBoundingClientRect(), t = tile.getBoundingClientRect();
    const cs = getComputedStyle(tile), ds = getComputedStyle(dot);
    return {
      dot: { w: Math.round(d.width), h: Math.round(d.height) },
      tile: { w: Math.round(t.width), h: Math.round(t.height) },
      tileRadius: cs.borderBottomRightRadius, tileRadiusStart: cs.borderBottomLeftRadius,
      insetBlockEnd: ds.insetBlockEnd, insetInlineEnd: ds.insetInlineEnd,
      overhangBottomPx: Math.round(d.bottom - t.bottom),
      overhangInlineEndPx: Math.round(t.left - d.left), // RTL: inline-end is the LEFT edge
      // fraction of the dot's area that lies outside the tile's border box
      outsideFraction: (() => {
        const ix = Math.max(0, Math.min(d.right, t.right) - Math.max(d.left, t.left));
        const iy = Math.max(0, Math.min(d.bottom, t.bottom) - Math.max(d.top, t.top));
        return Math.round((1 - (ix * iy) / (d.width * d.height)) * 100);
      })(),
    };
  });

  // H7: the picker's per-location online dots — what data drives them?
  out.locDots = await page.evaluate(() => {
    const cards = [...document.querySelectorAll(".loc-card")];
    return {
      cards: cards.length,
      withDot: cards.filter((c) => c.querySelector(".loc-online")).length,
      dotColors: [...new Set(cards.map((c) => { const d = c.querySelector(".loc-online"); return d ? getComputedStyle(d).backgroundColor : "none"; }))],
      dotBorderColors: [...new Set(cards.map((c) => { const d = c.querySelector(".loc-online"); return d ? getComputedStyle(d).borderColor : "none"; }))],
    };
  });

  // B1: which hero badges are actually visible in the scroller
  out.trustRow = await page.evaluate(() => {
    const row = document.querySelector(".trust-row");
    const rr = row.getBoundingClientRect();
    return {
      scrollWidth: row.scrollWidth, clientWidth: row.clientWidth, scrollLeft: row.scrollLeft,
      mask: getComputedStyle(row).webkitMaskImage || getComputedStyle(row).maskImage,
      pills: [...row.children].map((p) => {
        const r = p.getBoundingClientRect();
        const visible = Math.max(0, Math.min(r.right, rr.right) - Math.max(r.left, rr.left));
        return { text: p.textContent.trim(), width: Math.round(r.width), visiblePx: Math.round(visible),
                 visiblePct: Math.round((visible / r.width) * 100) };
      }),
    };
  });

  await writeFile(`${OUT}/crops.json`, JSON.stringify(out, null, 2));
  console.log(JSON.stringify(out, null, 2));
  await browser.close();
};
run();
