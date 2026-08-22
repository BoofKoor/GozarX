// Phase 2 UI audit — geometry / overflow / touch-target / typography probe.
// Renders the real built site against the mock backend at each audited width and reads COMPUTED
// values. Nothing here is inferred from the stylesheet.

import { chromium } from "playwright";
import { writeFile, mkdir } from "node:fs/promises";

const SITE = "http://127.0.0.1:3100";
const OUT = "/tmp/claude-0/-home-user-GozarX/c019534b-02b6-53f9-aaf3-f0202784f44e/scratchpad/out";
const WIDTHS = [360, 390, 412, 591];

async function settle(page) {
  await page.evaluate(async () => {
    const step = Math.floor(window.innerHeight * 0.8);
    for (let y = 0; y < document.body.scrollHeight; y += step) {
      window.scrollTo(0, y);
      await new Promise((r) => setTimeout(r, 50));
    }
    window.scrollTo(0, 0);
    await new Promise((r) => setTimeout(r, 150));
  });
  await page.evaluate(() => document.fonts?.ready);
  await page.waitForTimeout(400);
}

const probe = () => {
  const px = (v) => Math.round(v * 100) / 100;
  const cs = (el) => getComputedStyle(el);
  const rect = (el) => {
    const r = el.getBoundingClientRect();
    return { w: px(r.width), h: px(r.height), x: px(r.left), y: px(r.top + window.scrollY) };
  };
  const sel = (el) => {
    if (!el) return null;
    return (
      el.tagName.toLowerCase() +
      (el.id ? `#${el.id}` : "") +
      (el.className && typeof el.className === "string"
        ? "." + el.className.trim().split(/\s+/).slice(0, 3).join(".")
        : "")
    );
  };
  const out = {};

  // ---- document -------------------------------------------------------------------------
  out.doc = {
    innerWidth: window.innerWidth,
    scrollHeight: px(document.documentElement.scrollHeight),
    bodyScrollHeight: px(document.body.scrollHeight),
    docScrollWidth: px(document.documentElement.scrollWidth),
    horizontalOverflow: document.documentElement.scrollWidth > window.innerWidth,
    dpr: window.devicePixelRatio,
    dir: document.documentElement.dir,
    lang: document.documentElement.lang,
  };

  // ---- A1/A5: section boundaries -------------------------------------------------------
  out.sections = [...document.querySelectorAll("main section")].map((s, i) => {
    const c = cs(s);
    const r = rect(s);
    // first + last VISIBLE descendant with a text box, to measure the ink-to-ink gap
    const kids = [...s.querySelectorAll("*")].filter((el) => {
      const rr = el.getBoundingClientRect();
      return rr.height > 0 && rr.width > 0 && el.textContent.trim().length > 0;
    });
    const firstInk = kids.length ? rect(kids[0]) : null;
    let lastInk = null;
    for (const el of kids) {
      const rr = rect(el);
      if (!lastInk || rr.y + rr.h > lastInk.y + lastInk.h) lastInk = rr;
    }
    return {
      i,
      id: s.id || null,
      cls: s.className,
      paddingBlock: [c.paddingTop, c.paddingBottom],
      marginBlock: [c.marginTop, c.marginBottom],
      background: c.backgroundColor,
      backgroundImage: c.backgroundImage === "none" ? "none" : "gradient/image",
      borderTop: c.borderTopWidth + " " + c.borderTopStyle,
      rect: r,
      firstInkY: firstInk ? firstInk.y : null,
      lastInkBottom: lastInk ? px(lastInk.y + lastInk.h) : null,
    };
  });
  // ink-to-ink gaps between consecutive sections
  out.sectionGaps = [];
  for (let i = 1; i < out.sections.length; i++) {
    const a = out.sections[i - 1], b = out.sections[i];
    out.sectionGaps.push({
      between: `${a.id || a.cls}→${b.id || b.cls}`,
      boxGap: px(b.rect.y - (a.rect.y + a.rect.h)),
      inkGap: a.lastInkBottom != null && b.firstInkY != null ? px(b.firstInkY - a.lastInkBottom) : null,
      paddingSum: parseFloat(a.paddingBlock[1]) + parseFloat(b.paddingBlock[0]),
      bgChange: a.background !== b.background,
    });
  }

  // ---- A3: corner radii -----------------------------------------------------------------
  const radiusTargets = {
    "widget (main card)": ".widget",
    "loccard (flag card)": ".loccard",
    "locframe (map frame)": ".locframe",
    "cta (claim button)": ".cta",
    "ft-cta-btn (footer CTA)": ".ft-cta-btn",
    "step card": ".step",
    "loc-card (picker flag)": ".loc-card",
    "mvrow (mission card)": ".mvrow",
    "appcard": ".appcard",
    "statband": ".statband",
    "acc (faq)": ".acc",
    "trust-card": ".trust-card",
    "pill (hero trust)": ".trust-row .pill",
    "tb (trust badge)": ".tb",
    "chip (article link)": ".art-chips .chip",
    "eyebrow (section label)": ".eyebrow",
    "mvamt (reward badge)": ".mvamt",
    "step .num (icon box)": ".step .num",
    "mvrow .mi (icon box)": ".mvrow .mi",
    "statband .tile": ".statband .tile",
    "acct-btn (header account)": ".acct-btn",
    "burger": ".burger",
    "livepill": ".livepill",
    "flagmore (+N)": ".flagmore",
  };
  out.radii = {};
  for (const [k, q] of Object.entries(radiusTargets)) {
    const el = document.querySelector(q);
    if (!el) { out.radii[k] = null; continue; }
    const c = cs(el);
    out.radii[k] = {
      radius: c.borderTopLeftRadius,
      border: `${c.borderTopWidth} ${c.borderTopStyle} ${c.borderTopColor}`,
      rect: rect(el),
    };
  }

  // ---- A4: nested framed elements -------------------------------------------------------
  // count elements with a visible border whose ancestor chain already has >=1 bordered box
  const hasBorder = (el) => {
    const c = cs(el);
    return parseFloat(c.borderTopWidth) > 0 && c.borderTopStyle !== "none" &&
      c.borderTopColor !== "rgba(0, 0, 0, 0)" && c.borderTopColor !== "transparent";
  };
  out.nestedBorders = [];
  for (const el of document.querySelectorAll("main *, footer *")) {
    if (!hasBorder(el)) continue;
    const chain = [];
    let p = el.parentElement;
    while (p && p !== document.body) { if (hasBorder(p)) chain.push(sel(p)); p = p.parentElement; }
    if (chain.length >= 2) out.nestedBorders.push({ el: sel(el), depth: chain.length + 1, chain });
  }
  out.nestedBorders = out.nestedBorders.slice(0, 40);

  // ---- A6: text-align on subtitles ------------------------------------------------------
  out.textAlign = [...document.querySelectorAll(".sec-head, .sec-sub, .sec-title, .trust-card, .loccap")]
    .map((el) => ({ el: sel(el), textAlign: cs(el).textAlign, direction: cs(el).direction }));

  // ---- B: every flex container holding peer items ---------------------------------------
  out.flexSweep = [];
  for (const el of document.querySelectorAll("#app *")) {
    const c = cs(el);
    if (c.display !== "flex" && c.display !== "inline-flex") continue;
    const r = el.getBoundingClientRect();
    if (r.width === 0 || r.height === 0) continue;
    const kids = [...el.children].filter((k) => k.getBoundingClientRect().width > 0);
    if (kids.length < 2) continue;
    // does the last child sit on its own line? (compare its top to the first child's top)
    const tops = kids.map((k) => Math.round(k.getBoundingClientRect().top));
    const lines = [...new Set(tops)].sort((a, b) => a - b);
    const lastLineCount = tops.filter((t) => t === lines[lines.length - 1]).length;
    const contentW = [...kids].reduce((s, k) => s + k.getBoundingClientRect().width, 0) +
      (kids.length - 1) * (parseFloat(c.columnGap) || 0);
    out.flexSweep.push({
      el: sel(el),
      wrap: c.flexWrap,
      overflowX: c.overflowX,
      children: kids.length,
      lines: lines.length,
      orphanLastLine: lines.length > 1 && lastLineCount === 1,
      contentWidth: px(contentW),
      boxWidth: px(r.width),
      clipped: c.overflowX !== "visible" && el.scrollWidth > el.clientWidth + 1,
      scrollWidth: el.scrollWidth,
      clientWidth: el.clientWidth,
      mask: c.maskImage !== "none" || c.webkitMaskImage !== "none",
    });
  }

  // ---- B: scroll containers (any axis) ---------------------------------------------------
  out.scrollers = [];
  for (const el of document.querySelectorAll("#app *")) {
    const c = cs(el);
    const oy = c.overflowY, ox = c.overflowX;
    const scrollsY = (oy === "auto" || oy === "scroll") && el.scrollHeight > el.clientHeight + 1;
    const scrollsX = (ox === "auto" || ox === "scroll") && el.scrollWidth > el.clientWidth + 1;
    if (!scrollsY && !scrollsX) continue;
    out.scrollers.push({
      el: sel(el), overflowX: ox, overflowY: oy,
      scrollW: el.scrollWidth, clientW: el.clientWidth,
      scrollH: el.scrollHeight, clientH: el.clientHeight,
      maxBlockSize: c.maxHeight,
      overscrollBehavior: c.overscrollBehavior,
      mask: (c.maskImage !== "none" || c.webkitMaskImage !== "none"),
      hiddenFraction: scrollsY
        ? Math.round((1 - el.clientHeight / el.scrollHeight) * 100)
        : Math.round((1 - el.clientWidth / el.scrollWidth) * 100),
    });
  }

  // ---- C: touch targets -------------------------------------------------------------------
  const interactive = "a[href], button, [role=button], input, select, summary, [tabindex]:not([tabindex='-1'])";
  out.targets = [];
  for (const el of document.querySelectorAll(interactive)) {
    const r = el.getBoundingClientRect();
    if (r.width === 0 || r.height === 0) continue;
    const c = cs(el);
    out.targets.push({
      el: sel(el),
      text: (el.textContent || "").trim().slice(0, 34),
      w: px(r.width), h: px(r.height),
      display: c.display,
      paddingBlock: `${c.paddingTop}/${c.paddingBottom}`,
      fontSize: c.fontSize, lineHeight: c.lineHeight,
      under44: r.height < 44 || r.width < 44,
      under44Both: r.height < 44 && r.width < 44,
    });
  }

  // ---- C1/C2/D5 named groups -----------------------------------------------------------
  const group = (q) => {
    const els = [...document.querySelectorAll(q)];
    if (!els.length) return null;
    const e = els[0], c = cs(e), r = e.getBoundingClientRect();
    return {
      count: els.length, w: px(r.width), h: px(r.height),
      display: c.display, paddingBlock: `${c.paddingTop}/${c.paddingBottom}`,
      paddingInline: `${c.paddingLeft}/${c.paddingRight}`,
      fontSize: c.fontSize, lineHeight: c.lineHeight, fontWeight: c.fontWeight,
      color: c.color, background: c.backgroundColor,
      border: `${c.borderTopWidth} ${c.borderTopStyle} ${c.borderTopColor}`,
      radius: c.borderTopLeftRadius, cursor: c.cursor,
      textDecoration: c.textDecorationLine,
      heights: els.map((x) => px(x.getBoundingClientRect().height)),
    };
  };
  out.groups = {
    articleChip: group(".art-chips .chip"),
    footerColLink: group(".ft-col a"),
    footerMoreLink: group(".ft-more a"),
    footerMoreHeading: group(".ft-more-h"),
    eyebrow: group(".eyebrow"),
    trustBadge: group(".tb"),
    heroPill: group(".trust-row .pill"),
    locCard: group(".loc-card"),
    burger: group(".burger"),
    acctBtn: group(".acct-btn"),
    accHead: group(".acc-head"),
    linkMore: group(".link-more"),
    loccta: group(".loccta"),
    themeSwitch: group(".theme-switch"),
    ftLangBtn: group(".ft-langs button"),
    flagBig: group(".flagstrip .fbig"),
    flagMore: group(".flagmore"),
  };

  // ---- D6/D7: step + mission card anatomy --------------------------------------------------
  out.stepCards = [...document.querySelectorAll(".step")].map((s) => {
    const c = cs(s), num = s.querySelector(".num"), h3 = s.querySelector("h3"), p = s.querySelector("p");
    return {
      rect: rect(s), padding: `${c.paddingTop} ${c.paddingRight} ${c.paddingBottom} ${c.paddingLeft}`,
      display: c.display,
      num: num ? { ...rect(num), display: cs(num).display, marginBottom: cs(num).marginBottom } : null,
      title: h3 ? { ...rect(h3), fontSize: cs(h3).fontSize } : null,
      body: p ? rect(p) : null,
      deadSpaceBesideIcon: num && h3
        ? { w: px(s.getBoundingClientRect().width - parseFloat(c.paddingLeft) - parseFloat(c.paddingRight) - num.getBoundingClientRect().width),
            h: px(num.getBoundingClientRect().height) }
        : null,
    };
  });
  out.missionRows = [...document.querySelectorAll(".mvrow")].map((m) => {
    const c = cs(m);
    const mi = m.querySelector(".mi"), bd = m.querySelector(".mvbd"), amt = m.querySelector(".mvamt");
    const p = m.querySelector(".mvbd p");
    const lines = p ? Math.round(p.getBoundingClientRect().height / parseFloat(cs(p).lineHeight)) : null;
    return {
      rect: rect(m), gap: c.columnGap, padding: c.paddingTop + " " + c.paddingLeft,
      icon: mi ? rect(mi) : null,
      body: bd ? { ...rect(bd), flex: cs(bd).flex } : null,
      amount: amt ? { ...rect(amt), minWidth: cs(amt).minInlineSize || cs(amt).minWidth } : null,
      bodyLines: lines,
      title: (m.querySelector("h3") || {}).textContent,
    };
  });

  // ---- E1/E2: sticky header ---------------------------------------------------------------
  const hd = document.querySelector("header.hd");
  if (hd) {
    const c = cs(hd), r = hd.getBoundingClientRect();
    out.header = {
      position: c.position, top: c.top, zIndex: c.zIndex,
      height: px(r.height),
      background: c.backgroundColor,
      backdropFilter: c.backdropFilter || c.webkitBackdropFilter,
      borderBottom: `${c.borderBottomWidth} ${c.borderBottomStyle} ${c.borderBottomColor}`,
      boxShadow: c.boxShadow,
    };
  }
  out.scrollOffsets = {
    htmlScrollPaddingTop: cs(document.documentElement).scrollPaddingTop,
    bodyScrollPaddingTop: cs(document.body).scrollPaddingTop,
    htmlScrollBehavior: cs(document.documentElement).scrollBehavior,
    anchorTargets: [...document.querySelectorAll('a[href^="#"]')].map((a) => a.getAttribute("href")),
    idTargetsScrollMargin: [...document.querySelectorAll("main [id]")].map((el) => ({
      id: el.id, scrollMarginTop: cs(el).scrollMarginTop,
    })),
  };

  // ---- F1: line breaking on every centered subtitle ----------------------------------------
  out.subtitles = [...document.querySelectorAll(".sec-sub, .hero-copy .sub, .loccap")].map((el) => {
    const c = cs(el);
    const lh = parseFloat(c.lineHeight);
    const r = el.getBoundingClientRect();
    // measure each line's text via Range rects
    const range = document.createRange();
    range.selectNodeContents(el);
    const rects = [...range.getClientRects()].filter((x) => x.width > 1);
    const lineWidths = rects.map((x) => Math.round(x.width));
    return {
      el: sel(el),
      text: el.textContent.trim(),
      textWrap: c.textWrap || c.textWrapStyle || "normal",
      textAlign: c.textAlign,
      fontSize: c.fontSize, lineHeight: c.lineHeight,
      boxWidth: px(r.width), boxHeight: px(r.height),
      lines: lh ? Math.round(r.height / lh) : null,
      lineWidths,
      lastLineShare: lineWidths.length > 1
        ? Math.round((lineWidths[lineWidths.length - 1] / Math.max(...lineWidths)) * 100) : null,
    };
  });

  // ---- F2 / 4.4: hero headline gradient ----------------------------------------------------
  const h1 = document.querySelector(".hero-copy h1");
  const grad = document.querySelector(".hero-copy h1 .grad");
  if (h1) {
    const range = document.createRange();
    range.selectNodeContents(h1);
    const h1Rects = [...range.getClientRects()].filter((x) => x.width > 1);
    let gradRects = [];
    if (grad) {
      const gr = document.createRange();
      gr.selectNodeContents(grad);
      gradRects = [...gr.getClientRects()].filter((x) => x.width > 1);
    }
    out.heroHeadline = {
      h1Text: h1.textContent.trim(),
      h1FontSize: cs(h1).fontSize,
      h1TextWrap: cs(h1).textWrap,
      h1Lines: h1Rects.length,
      h1LineWidths: h1Rects.map((r) => Math.round(r.width)),
      gradSpanText: grad ? grad.textContent : null,
      gradFragments: gradRects.length,
      gradFragmentWidths: gradRects.map((r) => Math.round(r.width)),
      gradBoundingBox: grad ? rect(grad) : null,
      backgroundImage: grad ? cs(grad).backgroundImage : null,
      backgroundClip: grad ? (cs(grad).backgroundClip || cs(grad).webkitBackgroundClip) : null,
      boxDecorationBreak: grad ? (cs(grad).boxDecorationBreak || cs(grad).webkitBoxDecorationBreak) : null,
      heroTokens: {
        hero1: cs(document.getElementById("app")).getPropertyValue("--hero-1").trim(),
        hero2: cs(document.getElementById("app")).getPropertyValue("--hero-2").trim(),
      },
    };
  }

  // ---- G5 / H7 / H8: decorative overlays ----------------------------------------------------
  const livepill = document.querySelector(".livepill");
  const locframe = document.querySelector(".locframe");
  const worldmap = document.querySelector(".worldmap");
  out.locationsCard = {
    livepill: livepill ? { ...rect(livepill), position: cs(livepill).position, text: livepill.textContent.trim() } : null,
    locframe: locframe ? rect(locframe) : null,
    worldmap: worldmap ? { ...rect(worldmap), src: worldmap.getAttribute("src"),
      natural: `${worldmap.naturalWidth}x${worldmap.naturalHeight}` } : null,
    pillOverMapPct: livepill && worldmap ? {
      xPct: Math.round(((livepill.getBoundingClientRect().left - worldmap.getBoundingClientRect().left) /
            worldmap.getBoundingClientRect().width) * 100),
      yPct: Math.round(((livepill.getBoundingClientRect().top - worldmap.getBoundingClientRect().top) /
            worldmap.getBoundingClientRect().height) * 100),
      wPct: Math.round((livepill.getBoundingClientRect().width / worldmap.getBoundingClientRect().width) * 100),
    } : null,
    flags: [...document.querySelectorAll(".flagstrip .fbig")].map((f) => f.getAttribute("alt") || f.className),
    more: (document.querySelector(".flagmore") || {}).textContent || null,
    flagstripLines: (() => {
      const items = [...document.querySelectorAll(".flagstrip > *")];
      const tops = items.map((i) => Math.round(i.getBoundingClientRect().top));
      const uniq = [...new Set(tops)].sort((a, b) => a - b);
      return { lines: uniq.length, perLine: uniq.map((t) => tops.filter((x) => x === t).length) };
    })(),
  };
  const sb = document.querySelector(".statband");
  if (sb) {
    const after = getComputedStyle(sb, "::after");
    out.statband = {
      rect: rect(sb),
      afterContent: after.content,
      afterBackground: after.backgroundImage,
      afterInset: `${after.insetInlineStart}/${after.insetInlineEnd}`,
      afterHeight: after.blockSize || after.height,
      afterOpacity: after.opacity,
      figures: [...sb.querySelectorAll(".n")].map((n) => n.textContent.trim()),
      labels: [...sb.querySelectorAll(".l")].map((n) => n.textContent.trim()),
      onbDot: (() => {
        const d = sb.querySelector(".onb"), tile = sb.querySelector(".tile");
        if (!d || !tile) return null;
        const dr = d.getBoundingClientRect(), tr = tile.getBoundingClientRect();
        return {
          dot: { w: px(dr.width), h: px(dr.height) },
          overhangRight: px(dr.right - tr.right),
          overhangBottom: px(dr.bottom - tr.bottom),
          tileRadius: cs(tile).borderBottomRightRadius,
        };
      })(),
    };
  }

  // ---- I2: privacy/trust card alignment -----------------------------------------------------
  out.cardAlign = [...document.querySelectorAll(".trust-card, .step, .mvrow, .appcard, .acc, .loccard")]
    .map((el) => ({ el: sel(el), textAlign: cs(el).textAlign }));

  // ---- I3: footer column rhythm --------------------------------------------------------------
  out.footerCols = [...document.querySelectorAll(".ft-grid > *")].map((col) => {
    const links = [...col.querySelectorAll("a")];
    const c = cs(col);
    const gaps = [];
    for (let i = 1; i < links.length; i++) {
      gaps.push(px(links[i].getBoundingClientRect().top - links[i - 1].getBoundingClientRect().top));
    }
    return {
      el: sel(col), height: px(col.getBoundingClientRect().height),
      bottom: px(col.getBoundingClientRect().bottom + window.scrollY),
      links: links.length,
      linkPitch: gaps,
      linkLineHeight: links.length ? cs(links[0]).lineHeight : null,
      linkPadding: links.length ? `${cs(links[0]).paddingTop}/${cs(links[0]).paddingBottom}` : null,
      display: c.display,
    };
  });

  // ---- H1/H2: duplicated keyword list ---------------------------------------------------------
  const chips = [...document.querySelectorAll(".art-chips .chip")];
  const ftMore = document.querySelector(".ft-more");
  const ftLinks = ftMore ? [...ftMore.querySelectorAll("a")] : [];
  out.keywordLists = {
    chipCount: chips.length,
    chipTexts: chips.map((c) => c.textContent.trim()),
    chipHrefs: chips.map((c) => c.getAttribute("href")),
    footerCount: ftLinks.length,
    footerTexts: ftLinks.map((c) => c.textContent.trim()),
    footerHrefs: ftLinks.map((c) => c.getAttribute("href")),
    identicalTexts: JSON.stringify(chips.map((c) => c.textContent.trim())) ===
      JSON.stringify(ftLinks.map((c) => c.textContent.trim())),
    identicalHrefs: JSON.stringify(chips.map((c) => c.getAttribute("href"))) ===
      JSON.stringify(ftLinks.map((c) => c.getAttribute("href"))),
    ftMoreBox: ftMore ? rect(ftMore) : null,
    ftMoreDisplay: ftMore ? cs(ftMore).display : null,
    ftMoreFlexWrap: ftMore ? cs(ftMore).flexWrap : null,
    ftMoreGap: ftMore ? `${cs(ftMore).rowGap}/${cs(ftMore).columnGap}` : null,
    // heading + first link on the same visual line?
    headingSharesLine: (() => {
      const h = document.querySelector(".ft-more-h");
      if (!h || !ftLinks.length) return null;
      return Math.round(h.getBoundingClientRect().top) === Math.round(ftLinks[0].getBoundingClientRect().top);
    })(),
    footerLinesLayout: (() => {
      if (!ftMore) return null;
      const items = [...ftMore.children];
      const tops = items.map((i) => Math.round(i.getBoundingClientRect().top));
      const uniq = [...new Set(tops)].sort((a, b) => a - b);
      return uniq.map((t) => items.filter((i) => Math.round(i.getBoundingClientRect().top) === t)
        .map((i) => i.textContent.trim().slice(0, 26)));
    })(),
    separatorPseudo: (() => {
      if (!ftLinks.length) return null;
      const b = getComputedStyle(ftLinks[0], "::after"), a = getComputedStyle(ftLinks[0], "::before");
      return { after: b.content, before: a.content };
    })(),
  };

  // ---- H5: the number 29 ---------------------------------------------------------------------
  const bodyText = document.body.innerText;
  out.numberMentions = {
    "۲۹": (bodyText.match(/۲۹/g) || []).length,
    contexts: bodyText.split("\n").filter((l) => l.includes("۲۹")).map((l) => l.trim()).slice(0, 12),
  };

  // ---- I1: hover rules without a hover-capable guard -------------------------------------------
  out.hoverRules = (() => {
    const res = { total: 0, guarded: 0, unguarded: [], mediaBlocks: [] };
    for (const sheet of document.styleSheets) {
      let rules;
      try { rules = sheet.cssRules; } catch { continue; }
      const walk = (list, guarded) => {
        for (const r of list) {
          if (r.type === CSSRule.MEDIA_RULE) {
            const isHoverGuard = /hover\s*:\s*hover|any-hover/.test(r.conditionText || r.media.mediaText);
            if (isHoverGuard) res.mediaBlocks.push(r.conditionText || r.media.mediaText);
            walk(r.cssRules, guarded || isHoverGuard);
          } else if (r.type === CSSRule.SUPPORTS_RULE) {
            walk(r.cssRules, guarded);
          } else if (r.selectorText && r.selectorText.includes(":hover")) {
            res.total++;
            if (guarded) res.guarded++;
            else if (res.unguarded.length < 60) res.unguarded.push(r.selectorText);
          }
        }
      };
      walk(rules, false);
    }
    return res;
  })();

  // ---- I4: language switchers ---------------------------------------------------------------
  out.langControls = [...document.querySelectorAll("button, a")]
    .filter((el) => /English|فارسی|Persian/i.test(el.textContent || ""))
    .map((el) => {
      const r = el.getBoundingClientRect();
      return {
        el: sel(el), text: el.textContent.trim(),
        y: px(r.top + window.scrollY), w: px(r.width), h: px(r.height),
        visible: r.width > 0 && r.height > 0,
        display: cs(el).display,
        inHeader: !!el.closest("header"), inFooter: !!el.closest("footer"), inSheet: !!el.closest(".sheet"),
      };
    });

  // ---- tokens -------------------------------------------------------------------------------
  out.tokens = (() => {
    const app = document.getElementById("app");
    const names = new Set();
    for (const sheet of document.styleSheets) {
      let rules; try { rules = sheet.cssRules; } catch { continue; }
      const walk = (list) => { for (const r of list) {
        if (r.cssRules) walk(r.cssRules);
        else if (r.style) for (const p of r.style) if (p.startsWith("--")) names.add(p);
      } };
      walk(rules);
    }
    const resolved = {};
    for (const n of [...names].sort()) resolved[n] = getComputedStyle(app).getPropertyValue(n).trim();
    return { count: names.size, resolved };
  })();

  return out;
};

const run = async () => {
  await mkdir(OUT, { recursive: true });
  const browser = await chromium.launch({ executablePath: "/opt/pw-browsers/chromium-1194/chrome-linux/chrome" });
  const all = {};
  for (const width of WIDTHS) {
    const ctx = await browser.newContext({
      viewport: { width, height: 780 },
      deviceScaleFactor: 2,
      isMobile: true, hasTouch: true,
      locale: "fa-IR",
      extraHTTPHeaders: { "accept-language": "fa-IR,fa;q=0.9" },
      colorScheme: "dark",
    });
    await ctx.addCookies([
      { name: "theme", value: "dark", url: SITE },
      { name: "locale", value: "fa", url: SITE },
    ]);
    const page = await ctx.newPage();
    await page.goto(`${SITE}/`, { waitUntil: "networkidle", timeout: 45000 }).catch(() => {});
    await settle(page);
    all[width] = await page.evaluate(probe);
    await page.screenshot({ path: `${OUT}/home-fa-${width}-full.png`, fullPage: true });
    await page.screenshot({ path: `${OUT}/home-fa-${width}-fold.png` });
    await ctx.close();
    console.log(`measured ${width}: doc=${all[width].doc.scrollHeight}px`);
  }
  await browser.close();
  await writeFile(`${OUT}/geometry.json`, JSON.stringify(all, null, 2));
  console.log("wrote geometry.json");
};
run();
