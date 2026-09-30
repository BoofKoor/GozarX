import { NextResponse, type NextRequest } from "next/server";
import { LOCALE_COOKIE, pickLocale } from "@/lib/locale";

// Every page exists twice, prerendered: `app/[lang]` for fa and for en (C-61). This picks the one a
// request gets — the visitor's saved choice, else the browser's language, else fa — and REWRITES to
// it, so the address bar keeps the one public URL. Decision D3: SEO is Persian-only — no /en/ URLs
// and no hreflang; English is a display preference, never a second indexable site. A crawler sends
// neither a cookie nor Accept-Language, so it always reads the Persian page.
const LOCALE_PREFIX = /^\/(?:fa|en)(?=\/|$)/;

export function proxy(req: NextRequest) {
  const { pathname } = req.nextUrl;
  // `/fa/…` and `/en/…` are the rewrite's TARGETS, not addresses: reachable directly they would be
  // a second copy of every page for a crawler to find. Send them to the one public URL.
  const prefix = pathname.match(LOCALE_PREFIX);
  if (prefix) {
    const url = req.nextUrl.clone();
    url.pathname = pathname.slice(prefix[0].length) || "/";
    return NextResponse.redirect(url, 308);
  }
  const locale = pickLocale(req.cookies.get(LOCALE_COOKIE)?.value, req.headers.get("accept-language"));
  const url = req.nextUrl.clone();
  url.pathname = `/${locale}${pathname === "/" ? "" : pathname}`;
  // One URL, two languages: next.config's `headers()` keeps shared caches off these responses (a
  // Vary set here would not survive — Next writes its own).
  return NextResponse.rewrite(url);
}

export const config = {
  // Pages only: not the API, not Next's own assets, and not a file (robots.txt, sitemap.xml, sw.js,
  // the manifest, icons, flags, fonts, the OG images) — anything whose last segment has a dot.
  matcher: ["/((?!api/|_next/|[^?]*\\.[^/?]+$).*)"],
};
