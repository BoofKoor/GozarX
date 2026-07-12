import { cookies, headers } from "next/headers";
import { DEFAULT_LOCALE, isLocale, type Locale } from "@/lib/i18n";

// Server-side locale resolution used by page/layout server components so the first render matches.
// Order: an explicit `locale` cookie (the user's saved choice) → the browser's Accept-Language →
// fa. Language is auto-detected, then overridable from settings/footer — never in the header.
export async function getLocale(): Promise<Locale> {
  const store = await cookies();
  const raw = store.get("locale")?.value ?? "";
  if (isLocale(raw)) return raw;
  return localeFromAcceptLanguage((await headers()).get("accept-language"));
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
