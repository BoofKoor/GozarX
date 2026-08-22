// Final gaps: Cyrillic coverage of the bundled fonts, the pill family (D5), nested FRAMED boxes
// (A4, tightened so a status dot no longer counts as a "frame"), and the D1 link inventory.

import { chromium } from "playwright";
import { writeFile } from "node:fs/promises";

const SITE = "http://127.0.0.1:3100";
const OUT = "/tmp/claude-0/-home-user-GozarX/c019534b-02b6-53f9-aaf3-f0202784f44e/scratchpad/out";

const probe = () => {
  const cs = (el) => getComputedStyle(el);
  const px = (v) => Math.round(v * 10) / 10;
  const out = {};

  // ---- 4.2: does either bundled webfont carry Cyrillic? ------------------------------------
  out.fonts = {
    faces: [...document.fonts].map((f) => ({ family: f.family, status: f.status, unicodeRange: f.unicodeRange })),
    checks: {
      "Yekan Bakh VF · Cyrillic Привет": document.fonts.check('16px "Yekan Bakh VF"', "Привет"),
      "Yekan Bakh VF · Persian سلام": document.fonts.check('16px "Yekan Bakh VF"', "سلام"),
      "Inter Variable · Cyrillic Привет": document.fonts.check('16px "Inter Variable"', "Привет"),
      "Inter Variable · Latin Hello": document.fonts.check('16px "Inter Variable"', "Hello"),
    },
  };
  // what --font resolves to for a locale the stylesheet doesn't know
  const app = document.getElementById("app");
  const before = app.getAttribute("data-locale");
  out.fontFallback = { faFont: cs(app).fontFamily, faTokenFont: cs(app).getPropertyValue("--font").trim(),
    faLhBody: cs(app).getPropertyValue("--lh-body").trim() };
  app.setAttribute("data-locale", "ru");
  out.fontFallback.ruFont = cs(app).fontFamily;
  out.fontFallback.ruTokenFont = cs(app).getPropertyValue("--font").trim() || "(UNSET)";
  out.fontFallback.ruLhBody = cs(app).getPropertyValue("--lh-body").trim() || "(UNSET)";
  out.fontFallback.ruLineHeight = cs(app).lineHeight;
  app.setAttribute("data-locale", before);

  // ---- D5: the pill family -----------------------------------------------------------------
  const pillish = { ".eyebrow (section label)": ".eyebrow", ".tb (trust badge)": ".tb",
    ".trust-row .pill (hero badge)": ".trust-row .pill", ".art-chips .chip (ARTICLE LINK)": ".art-chips .chip",
    ".livepill": ".livepill", ".app-rec (recommendation)": ".appcard .app-rec", ".rw (reward)": ".mvamt" };
  out.pills = {};
  for (const [k, q] of Object.entries(pillish)) {
    const el = document.querySelector(q);
    if (!el) { out.pills[k] = null; continue; }
    const c = cs(el);
    out.pills[k] = {
      tag: el.tagName, classes: el.className,
      isLink: el.tagName === "A" || el.closest("a") === el, href: el.getAttribute?.("href") || null,
      radius: c.borderTopLeftRadius, border: `${c.borderTopWidth} ${c.borderTopStyle}`,
      padding: `${c.paddingTop} ${c.paddingLeft}`, fontSize: c.fontSize, fontWeight: c.fontWeight,
      color: c.color, background: c.backgroundColor,
      cursor: c.cursor, textDecoration: c.textDecorationLine,
      h: px(el.getBoundingClientRect().height),
      sharedClass: [...el.classList].join(" "),
      hasArrow: !!el.querySelector("svg"),
    };
  }

  // ---- A4: nested FRAMED boxes (a box with a border AND a padding >= 6px — i.e. a container,
  //          not a dot or a badge tab) ------------------------------------------------------
  const framed = (el) => {
    const c = cs(el);
    const bw = parseFloat(c.borderTopWidth);
    if (!(bw > 0) || c.borderTopStyle === "none") return false;
    if (c.borderTopColor === "rgba(0, 0, 0, 0)") return false;
    const r = el.getBoundingClientRect();
    return r.width >= 40 && r.height >= 24;
  };
  out.framedChains = [];
  for (const el of document.querySelectorAll("main *, footer *")) {
    if (!framed(el)) continue;
    const chain = [];
    let p = el.parentElement;
    while (p && p !== document.body) { if (framed(p)) chain.push(p.className || p.tagName); p = p.parentElement; }
    if (chain.length >= 2)
      out.framedChains.push({ el: (el.className || el.tagName).toString().slice(0, 40), depth: chain.length + 1,
        chain: chain.map((c) => String(c).slice(0, 30)) });
  }
  // dedupe by signature
  const seen = new Set();
  out.framedChains = out.framedChains.filter((f) => {
    const k = f.el + "|" + f.chain.join(">");
    if (seen.has(k)) return false; seen.add(k); return true;
  });

  // ---- D1: every "text link" rendering on the page -----------------------------------------
  out.textLinks = [];
  for (const a of document.querySelectorAll("main a[href], footer a[href]")) {
    const r = a.getBoundingClientRect();
    if (r.width === 0) continue;
    const c = cs(a);
    out.textLinks.push({
      cls: a.className || "(no class)", text: (a.textContent || "").trim().slice(0, 26),
      href: a.getAttribute("href"),
      hasArrow: !!a.querySelector("svg"),
      display: c.display, fontSize: c.fontSize, fontWeight: c.fontWeight, color: c.color,
      textDecoration: c.textDecorationLine, border: parseFloat(c.borderTopWidth) > 0,
      background: c.backgroundColor !== "rgba(0, 0, 0, 0)",
      insideCard: !!a.closest(".loccard, .trust-card, .step, .mvrow, .appcard, .acc, .card"),
      dividerAbove: (() => {
        const prev = a.previousElementSibling;
        if (!prev) {
          const pp = a.parentElement;
          return pp && parseFloat(cs(pp).borderTopWidth) > 0;
        }
        return parseFloat(cs(prev).borderBottomWidth) > 0 || prev.classList.contains("locdiv");
      })(),
      isBlockRow: c.display === "flex" && r.width > 200,
    });
  }
  // group by visual signature
  const sig = (l) => `${l.hasArrow ? "arrow" : "no-arrow"}|${l.background ? "filled" : "plain"}|${l.border ? "bordered" : "unbordered"}|${l.insideCard ? "in-card" : "outside-card"}|${l.dividerAbove ? "divider" : "no-divider"}`;
  const groups = {};
  for (const l of out.textLinks) (groups[sig(l)] ||= []).push({ cls: l.cls, text: l.text, fs: l.fontSize, color: l.color });
  out.textLinkGroups = Object.fromEntries(Object.entries(groups).map(([k, v]) => [k, { count: v.length, samples: v.slice(0, 4) }]));

  return out;
};

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
    scrollTo(0, 0); await new Promise(r => setTimeout(r, 200));
  });
  await page.evaluate(() => document.fonts?.ready);
  await page.waitForTimeout(400);
  const out = await page.evaluate(probe);
  await writeFile(`${OUT}/final.json`, JSON.stringify(out, null, 2));
  console.log(JSON.stringify(out.fonts, null, 2));
  console.log("\nFONT FALLBACK FOR AN UNKNOWN LOCALE:", JSON.stringify(out.fontFallback, null, 2));
  console.log("\n=== D5 PILL FAMILY ===");
  for (const [k, v] of Object.entries(out.pills)) {
    if (!v) { console.log(`  ${k}: absent`); continue; }
    console.log(`  ${k.padEnd(34)} <${v.tag}> class="${v.sharedClass}" link=${v.isLink} r=${v.radius} border=${v.border} pad=${v.padding} fs=${v.fontSize} cursor=${v.cursor} deco=${v.textDecoration} arrow=${v.hasArrow} h=${v.h}`);
  }
  console.log("\n=== A4 NESTED FRAMED BOXES (>=3 deep) ===");
  for (const f of out.framedChains) console.log(`  depth=${f.depth}  ${f.el}  inside  ${f.chain.join(" ⊂ ")}`);
  console.log(`  total distinct: ${out.framedChains.length}`);
  console.log("\n=== D1 TEXT-LINK RENDERINGS ===");
  for (const [k, v] of Object.entries(out.textLinkGroups))
    console.log(`  [${k}] ×${v.count}  e.g. ${v.samples.map((s) => `${s.cls}«${s.text}»`).join(", ").slice(0, 120)}`);
  await browser.close();
};
run();
