// Phase 1 — copy and terminology probe. READ-ONLY.
// Renders every in-scope page and asks three questions of the TEXT rather than the pixels:
//   1. which technical terms does a non-technical reader meet, and is any of them ever defined?
//   2. does one action carry one name across the whole flow, or several?
//   3. what does the site say about why it is free, who runs it, and what it collects?

import { chromium } from "playwright";
import { writeFile } from "node:fs/promises";

const SITE = "http://127.0.0.1:3100";
const MOCK = "http://127.0.0.1:8000";
const ANDROID_UA =
  "Mozilla/5.0 (Linux; Android 12; SM-A125F) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Mobile Safari/537.36";

const ROUTES = ["/", "/status", "/locations", "/guides", "/guides/android", "/guides/ios", "/faq", "/about", "/contact", "/privacy", "/terms"];

// The jargon a first-time, non-technical user meets. Each entry: the term, and the regexes that
// would count as an explanation of it appearing NEAR it.
const TERMS = [
  { term: "کانفیگ", label: "config" },
  { term: "لوکیشن", label: "location" },
  { term: "VLESS", label: "VLESS" },
  { term: "V2Ray", label: "V2Ray" },
  { term: "vless://", label: "the link scheme itself" },
  { term: "استریک", label: "streak" },
  { term: "پینگ", label: "ping" },
  { term: "کلیپ‌بورد", label: "clipboard" },
  { term: "وب‌اپ", label: "web app / PWA" },
  { term: "PWA", label: "PWA" },
  { term: "ساب", label: "subscription" },
  { term: "اشتراک", label: "subscription (Persian)" },
  { term: "پروتکل", label: "protocol" },
  { term: "DNS", label: "DNS" },
  { term: "سرور", label: "server" },
];

const setState = (n) =>
  fetch(`${MOCK}/__state`, { method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify({ name: n }) });

const browser = await chromium.launch({ executablePath: "/opt/pw-browsers/chromium-1194/chrome-linux/chrome" });
const out = { pages: {}, terms: {}, actionNames: {}, trust: {} };

await setState("delivered");
const ctx = await browser.newContext({
  viewport: { width: 360, height: 640 }, deviceScaleFactor: 1, isMobile: true, hasTouch: true,
  userAgent: ANDROID_UA, locale: "fa-IR",
  extraHTTPHeaders: { "accept-language": "fa-IR,fa;q=0.9" },
});
await ctx.addCookies([
  { name: "locale", value: "fa", url: SITE },
  { name: "theme", value: "dark", url: SITE },
]);
const page = await ctx.newPage();

for (const route of ROUTES) {
  await page.goto(SITE + route, { waitUntil: "networkidle", timeout: 45000 }).catch(() => {});
  await page.evaluate(async () => {
    const s = Math.floor(window.innerHeight * 0.8);
    for (let y = 0; y < document.body.scrollHeight; y += s) { window.scrollTo(0, y); await new Promise((r) => setTimeout(r, 40)); }
    window.scrollTo(0, 0);
  }).catch(() => {});
  await page.waitForTimeout(300);
  const data = await page.evaluate(() => ({
    title: document.title,
    h1: [...document.querySelectorAll("h1")].map((h) => h.innerText.trim()),
    h2: [...document.querySelectorAll("h2")].map((h) => h.innerText.trim()),
    text: document.body.innerText.replace(/\s+/g, " ").trim(),
    // every button/link LABEL on the page — the raw material for "does one action have one name"
    labels: [...document.querySelectorAll("button, a[href]")]
      .filter((el) => { const r = el.getBoundingClientRect(); return r.width > 0 && r.height > 0; })
      .map((el) => (el.getAttribute("aria-label") || el.innerText).replace(/\s+/g, " ").trim())
      .filter(Boolean),
  }));
  out.pages[route] = data;
  console.log(`  ${route}  title="${data.title.slice(0, 50)}"  ${data.text.length} chars`);
}

// --- term census across the whole corpus -------------------------------------------------------
const corpus = Object.entries(out.pages).map(([r, p]) => ({ r, t: p.text }));
for (const { term, label } of TERMS) {
  const hits = corpus.filter((c) => c.t.includes(term));
  out.terms[term] = {
    label,
    pages: hits.map((h) => h.r),
    total: hits.reduce((s, h) => s + (h.t.split(term).length - 1), 0),
    // an explanation would be the term followed within ~120 chars by a definitional phrase
    definedNear: hits.some((h) => {
      const i = h.t.indexOf(term);
      const win = h.t.slice(Math.max(0, i - 120), i + 160);
      return /یعنی|چیست|به معنای|همان|عبارت است از|is a |means |refers to/.test(win);
    }),
  };
}
console.log("\n  TERM CENSUS");
for (const [term, v] of Object.entries(out.terms)) {
  if (v.total) console.log(`    ${term.padEnd(12)} ×${String(v.total).padStart(3)}  on ${v.pages.length} pages  defined=${v.definedNear}`);
}

// --- does one action carry one name? ------------------------------------------------------------
const ACTIONS = {
  "claim a config": [/دریافت کانفیگ/, /کانفیگ رایگان امروز/, /بگیر/, /دریافت$/, /کانفیگ.*بگیر/],
  "copy the link": [/^کپی$/, /کپی کن/, /کپی شد/],
  "change location": [/تغییر لوکیشن/, /لوکیشن را عوض/, /عوض کردن/],
  "invite a friend": [/دعوت دوستان/, /لینک دعوت/, /اشتراک‌گذاری/, /دعوت کن/],
};
for (const [action, pats] of Object.entries(ACTIONS)) {
  const found = new Set();
  for (const p of Object.values(out.pages)) for (const l of p.labels) for (const re of pats) if (re.test(l)) found.add(l);
  out.actionNames[action] = [...found];
  console.log(`\n  "${action}" is labelled: ${JSON.stringify([...found])}`);
}

// --- trust signals -------------------------------------------------------------------------------
const TRUST = {
  "why it is free": /چرا رایگان|رایگان است چون|درآمد|هزینه.*تامین|تبلیغ|donation|حامی/,
  "who runs it": /تیم|ما کی|درباره ما|شرکت|سازنده|توسط/,
  "what is collected": /جمع‌آوری|ذخیره می‌کنیم|لاگ|اطلاعات شخصی|کوکی|داده/,
  "no logs claim": /لاگ نمی|بدون لاگ|ثبت نمی‌کنیم|no.?log/i,
};
for (const [k, re] of Object.entries(TRUST)) {
  const hits = corpus.filter((c) => re.test(c.t)).map((c) => c.r);
  out.trust[k] = hits;
  console.log(`  trust "${k}": ${hits.length ? hits.join(", ") : "NOT FOUND on any page"}`);
}

// --- the homepage's own above-the-fold text, verbatim ---------------------------------------------
await page.goto(SITE + "/", { waitUntil: "networkidle", timeout: 45000 });
await page.waitForTimeout(400);
out.homeFold = await page.evaluate(() => {
  const fold = window.innerHeight;
  const seen = [];
  const w = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
  let n;
  while ((n = w.nextNode())) {
    const s = n.nodeValue.trim(); if (!s) continue;
    const el = n.parentElement; if (!el) continue;
    const r = el.getBoundingClientRect();
    if (r.top < fold && r.bottom > 0 && r.width > 0) seen.push(s);
  }
  return seen;
});
console.log(`\n  HOME ABOVE THE FOLD (fa, 360×640):\n${out.homeFold.map((s) => "    " + s).join("\n")}`);

// --- the FAQ, in full: is "what is a config" answered? --------------------------------------------
await page.goto(SITE + "/faq", { waitUntil: "networkidle", timeout: 45000 });
await page.waitForTimeout(400);
out.faq = await page.evaluate(() =>
  [...document.querySelectorAll("details, .faq-item, li")].map((d) => d.innerText.replace(/\s+/g, " ").trim()).filter((t) => t.length > 8),
);
console.log(`\n  FAQ items (${out.faq.length}):\n${out.faq.map((f) => "    · " + f.slice(0, 120)).join("\n")}`);

await ctx.close();
await browser.close();
await setState("first");
await writeFile(new URL("../copy.json", import.meta.url).pathname, JSON.stringify(out, null, 2));
console.log("\ncopy -> audit/copy.json");
