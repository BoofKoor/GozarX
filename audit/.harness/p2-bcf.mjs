// B (overflow / wrap / orphan), C (touch targets), F (line breaking) — focused.
import { chromium } from "playwright";
import { writeFile } from "node:fs/promises";

const SITE = "http://127.0.0.1:3100";
const OUT = "/tmp/claude-0/-home-user-GozarX/c019534b-02b6-53f9-aaf3-f0202784f44e/scratchpad/out";
const WIDTHS = [360, 390, 412, 591];

const probe = () => {
  const px = (v) => Math.round(v * 10) / 10;
  const cs = (el) => getComputedStyle(el);
  const sig = (el) => el.tagName.toLowerCase() +
    (el.id ? `#${el.id}` : "") +
    (typeof el.className === "string" && el.className.trim()
      ? "." + el.className.trim().split(/\s+/).filter(c => !["reveal","in"].includes(c)).slice(0,3).join(".") : "");
  const out = {};

  // ---- B5 GLOBAL SWEEP: every ROW flex container with >=2 peer children -------------------
  out.rows = [];
  for (const el of document.querySelectorAll("#app *")) {
    const c = cs(el);
    if (c.display !== "flex" && c.display !== "inline-flex") continue;
    if (!c.flexDirection.startsWith("row")) continue;
    const r = el.getBoundingClientRect();
    if (r.width === 0 || r.height === 0) continue;
    const kids = [...el.children].filter(k => { const kr = k.getBoundingClientRect(); return kr.width > 0 && kr.height > 0; });
    if (kids.length < 2) continue;
    const tops = kids.map(k => Math.round(k.getBoundingClientRect().top));
    const lines = [...new Set(tops)].sort((a,b)=>a-b);
    const perLine = lines.map(t => tops.filter(x => x === t).length);
    const gapX = parseFloat(c.columnGap) || 0;
    const natural = kids.reduce((s,k)=>s+k.getBoundingClientRect().width,0) + (kids.length-1)*gapX;
    out.rows.push({
      el: sig(el),
      wrap: c.flexWrap, overflowX: c.overflowX, justify: c.justifyContent,
      kids: kids.length, lines: lines.length, perLine,
      orphan: lines.length > 1 && perLine[perLine.length-1] === 1 && kids.length > 2,
      naturalWidth: px(natural), boxWidth: px(r.width),
      wouldOverflow: natural > r.width + 1,
      clipped: c.overflowX !== "visible" && el.scrollWidth > el.clientWidth + 1,
      hiddenPx: Math.max(0, el.scrollWidth - el.clientWidth),
      mask: c.maskImage !== "none" || c.webkitMaskImage !== "none",
      scrollSnap: c.scrollSnapType,
      childMinWidth: kids.map(k => cs(k).minWidth).filter(v => v !== "0px" && v !== "auto")[0] || null,
      childFlex: [...new Set(kids.map(k => cs(k).flex))].slice(0,3),
    });
  }

  // ---- C: touch targets, grouped -------------------------------------------------------
  const sels = {
    "C1 article chip (.art-chips .chip)": ".art-chips .chip",
    "C2 footer column link (.ft-col a)": ".ft-col a",
    "C2 footer keyword link (.ft-more a)": ".ft-more a",
    "C2 footer bottom link (.ft-bottom a)": ".ft-bottom a",
    "C3 flag card (.loc-card)": ".loc-card",
    "C3 big flag (.flagstrip .fbig)": ".flagstrip .fbig",
    "C4 burger (.burger)": ".burger",
    "C4 account (.acct-btn)": ".acct-btn",
    "C5 accordion row (.acc-head)": ".acc-head",
    "CTA (.cta)": ".cta",
    "footer CTA (.ft-cta-btn)": ".ft-cta-btn",
    "loccta (.loccta)": ".loccta",
    "link-more (.link-more)": ".link-more",
    "appcard (.appcard)": ".appcard",
    "mvrow (.mvrow)": ".mvrow",
    "lang button (.ft-langs button)": ".ft-langs button",
    "theme switch (.theme-switch)": ".theme-switch",
    "sheet navlink (.sheet .navlink)": ".sheet .navlink",
  };
  out.targets = {};
  for (const [name, q] of Object.entries(sels)) {
    const els = [...document.querySelectorAll(q)].filter(e => e.getBoundingClientRect().width > 0);
    if (!els.length) { out.targets[name] = null; continue; }
    const c = cs(els[0]);
    const hs = els.map(e => px(e.getBoundingClientRect().height));
    const ws = els.map(e => px(e.getBoundingClientRect().width));
    out.targets[name] = {
      count: els.length,
      h: { min: Math.min(...hs), max: Math.max(...hs) },
      w: { min: Math.min(...ws), max: Math.max(...ws) },
      display: c.display, fontSize: c.fontSize, lineHeight: c.lineHeight,
      paddingBlock: `${c.paddingTop}/${c.paddingBottom}`,
      paddingInline: `${c.paddingLeft}/${c.paddingRight}`,
      minHeight: c.minHeight,
      under44: hs.filter(h => h < 44).length,
      // vertical pitch between consecutive items (gap between tap areas)
      pitch: els.length > 1 ? px(els[1].getBoundingClientRect().top - els[0].getBoundingClientRect().top) : null,
      verticalGap: (() => {
        if (els.length < 2) return null;
        const a = els[0].getBoundingClientRect(), b = els[1].getBoundingClientRect();
        return Math.round(b.top - a.bottom) >= 0 ? px(b.top - a.bottom) : null;
      })(),
    };
  }
  // full list of interactive elements under 44 in BOTH axes
  out.tinyTargets = [...document.querySelectorAll("a[href],button,[role=button],input,select")]
    .map(e => ({ el: sig(e), t: (e.textContent||"").trim().slice(0,26),
                 w: px(e.getBoundingClientRect().width), h: px(e.getBoundingClientRect().height) }))
    .filter(x => x.w > 0 && x.h > 0 && x.h < 44)
    .slice(0, 60);

  // ---- F1: line breaking -----------------------------------------------------------------
  out.subtitles = [...document.querySelectorAll(".sec-sub, .hero-copy .sub, .loccap, .hero-copy h1, .sec-title")].map(el => {
    const c = cs(el);
    const range = document.createRange(); range.selectNodeContents(el);
    const rects = [...range.getClientRects()].filter(x => x.width > 1);
    // Reconstruct per-line text by walking characters (needed to see WHERE it breaks)
    const text = el.textContent.replace(/\s+/g, " ").trim();
    const linesText = [];
    try {
      const tn = document.createTreeWalker(el, NodeFilter.SHOW_TEXT);
      let cur = "", lastTop = null;
      let node;
      while ((node = tn.nextNode())) {
        for (let i = 0; i < node.textContent.length; i++) {
          const rr = document.createRange();
          rr.setStart(node, i); rr.setEnd(node, i + 1);
          const b = rr.getBoundingClientRect();
          if (b.height === 0) { cur += node.textContent[i]; continue; }
          const top = Math.round(b.top);
          if (lastTop !== null && Math.abs(top - lastTop) > 4) { linesText.push(cur.trim()); cur = ""; }
          lastTop = top; cur += node.textContent[i];
        }
      }
      if (cur.trim()) linesText.push(cur.trim());
    } catch { /* best effort */ }
    return {
      el: sig(el), text,
      textWrap: c.textWrap, textAlign: c.textAlign, fontSize: c.fontSize, lineHeight: c.lineHeight,
      boxWidth: px(el.getBoundingClientRect().width),
      lineCount: rects.length,
      lineWidths: rects.map(r => Math.round(r.width)),
      linesText,
      lastLineWords: linesText.length ? linesText[linesText.length-1].split(" ").length : null,
      lastLineRatio: rects.length > 1 ? Math.round(rects[rects.length-1].width / Math.max(...rects.map(r=>r.width)) * 100) : null,
    };
  });

  // ---- F3: location names -------------------------------------------------------------
  out.locNames = [...document.querySelectorAll(".loc-card .nm")].map(el => ({
    text: el.textContent, scrollW: el.scrollWidth, clientW: el.clientWidth,
    truncated: el.scrollWidth > el.clientWidth + 1,
    overflow: cs(el).overflow, textOverflow: cs(el).textOverflow, direction: cs(el).direction,
  })).filter(x => x.truncated);

  return out;
};

const run = async () => {
  const browser = await chromium.launch({ executablePath: "/opt/pw-browsers/chromium-1194/chrome-linux/chrome" });
  const all = {};
  for (const width of WIDTHS) {
    const ctx = await browser.newContext({
      viewport: { width, height: 780 }, deviceScaleFactor: 2, isMobile: true, hasTouch: true,
      locale: "fa-IR", extraHTTPHeaders: { "accept-language": "fa-IR,fa;q=0.9" }, colorScheme: "dark",
    });
    await ctx.addCookies([{ name: "theme", value: "dark", url: SITE }, { name: "locale", value: "fa", url: SITE }]);
    const page = await ctx.newPage();
    await page.goto(`${SITE}/`, { waitUntil: "networkidle", timeout: 45000 }).catch(() => {});
    await page.evaluate(async () => {
      for (let y = 0; y < document.body.scrollHeight; y += 600) { scrollTo(0, y); await new Promise(r=>setTimeout(r,40)); }
      scrollTo(0,0); await new Promise(r=>setTimeout(r,200));
    });
    await page.evaluate(() => document.fonts?.ready);
    await page.waitForTimeout(300);
    all[width] = await page.evaluate(probe);
    await ctx.close();
    console.log("done", width);
  }
  await browser.close();
  await writeFile(`${OUT}/bcf.json`, JSON.stringify(all, null, 2));
};
run();
