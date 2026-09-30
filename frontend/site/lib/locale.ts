import { DEFAULT_LOCALE, isLocale, type Locale } from "@/lib/i18n";

// Which language a request gets — decided ONCE, in `proxy.ts`, which rewrites the request onto the
// matching static tree (`app/[lang]/…`). Order: an explicit `locale` cookie (the visitor's saved
// choice) → the browser's Accept-Language → fa. Decision D3: SEO is Persian-only, so there is one
// public URL per page and no /en/ tree — a crawler, which sends neither, always reads Persian.
export const LOCALE_COOKIE = "locale";

export function pickLocale(cookie: string | undefined, acceptLanguage: string | null): Locale {
  if (cookie && isLocale(cookie)) return cookie;
  return localeFromAcceptLanguage(acceptLanguage);
}

// Pick fa/en by whichever appears first in Accept-Language; default fa (the primary audience). e.g.
// "en-US,en;q=0.9" → en, "fa-IR,fa;q=0.9,en;q=0.8" → fa, "de-DE" or missing → fa.
export function localeFromAcceptLanguage(header: string | null): Locale {
  const h = (header ?? "").toLowerCase();
  const fa = h.indexOf("fa");
  const en = h.indexOf("en");
  if (fa === -1 && en === -1) return DEFAULT_LOCALE;
  if (fa === -1) return "en";
  if (en === -1) return "fa";
  return fa <= en ? "fa" : "en";
}

// A page's PUBLIC path. A page is rendered as `/fa/…` or `/en/…` (the rewrite's target) while the
// browser shows `/…`, so anything that compares paths — the header's "you are here" marker —
// strips the segment first, or the prerendered HTML and the hydrated page would disagree.
export function publicPath(pathname: string): string {
  return pathname.replace(/^\/(?:fa|en)(?=\/|$)/, "") || "/";
}
