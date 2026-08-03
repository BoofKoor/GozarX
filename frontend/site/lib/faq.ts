// Server-side read of the editable FAQ (/api/public/faq). Same pattern as lib/siteCopy.ts: runs in
// the Next server, hits BACKEND_ORIGIN directly, ISR-revalidated so an admin edit shows within
// ~5 minutes without a redeploy.
//
// Falls back to the in-code FAQ_ITEMS on ANY failure and on an empty response. Empty matters: a
// fresh install before the seeder runs, a backend outage, and `next build` with no backend all
// return nothing, and rendering an empty FAQ page would be worse than rendering the built-in list.
// The consequence — an operator can't unpublish every single question and get a blank page — is the
// right trade: they can still empty a category, and one blank page is never the intent.

import { FAQ_ITEMS, type FaqItem } from "@/lib/content";
import type { Locale } from "@/lib/i18n";

const BACKEND = (process.env.BACKEND_ORIGIN ?? "http://127.0.0.1:8000").replace(/\/+$/, "");
const REVALIDATE = 300;

export async function fetchFaqItems(locale: Locale): Promise<FaqItem[]> {
  try {
    const res = await fetch(`${BACKEND}/api/public/faq?locale=${locale}`, {
      next: { revalidate: REVALIDATE },
    });
    if (!res.ok) return FAQ_ITEMS[locale];
    const data = (await res.json()) as FaqItem[];
    if (!Array.isArray(data) || data.length === 0) return FAQ_ITEMS[locale];
    // Guard the shape too — a malformed row must not render as "undefined" in the accordion.
    const items = data.filter((i) => i && typeof i.q === "string" && typeof i.a === "string");
    return items.length > 0 ? items : FAQ_ITEMS[locale];
  } catch {
    return FAQ_ITEMS[locale];
  }
}
