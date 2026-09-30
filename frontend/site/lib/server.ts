import { notFound } from "next/navigation";
import { isLocale, type Locale } from "@/lib/i18n";

// The locale of a page under `app/[lang]` — the segment `proxy.ts` rewrote the request onto. Pages
// read it from their params instead of from the request (cookies, Accept-Language), because reading
// the request made every page dynamic: nothing was cached, and each visit re-rendered the whole tree
// (C-61). Anything else in the segment (a direct `/de/…`) is not a page.
export type LangParams = Promise<{ lang: string }>;

export async function localeOf(params: LangParams): Promise<Locale> {
  const { lang } = await params;
  if (!isLocale(lang)) notFound();
  return lang;
}

