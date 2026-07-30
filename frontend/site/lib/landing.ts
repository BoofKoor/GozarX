// Server-side reads of the SEO keyword landings (/api/public/pages) — the site's ONLY server→
// backend fetches. They run in the Next server (never the browser), so they hit BACKEND_ORIGIN
// directly (http://app:8000 inside compose; set in BOTH stages of docker/Dockerfile.site).
//
// Failure is always graceful (null / []): `next build` runs inside Docker with no backend up, and a
// transient backend outage must degrade to a 404/landing-less sitemap — never crash a render.
// `revalidate` gives ISR semantics: admin edits appear within ~5 minutes without a redeploy.

import type { Locale } from "@/lib/i18n";

const BACKEND = (process.env.BACKEND_ORIGIN ?? "http://127.0.0.1:8000").replace(/\/+$/, "");
const REVALIDATE = 300;

export interface LandingSummary {
  slug: string;
  locale: string;
  title: string;
  meta_description: string;
  location_remark: string | null;
  updated_at: string | null;
}

export interface Landing extends LandingSummary {
  heading: string | null;
  body: string; // trusted admin-authored HTML (see backend admin/landing.py) — rendered verbatim
}

export async function fetchLanding(slug: string, locale: Locale): Promise<Landing | null> {
  try {
    const res = await fetch(
      `${BACKEND}/api/public/pages/${encodeURIComponent(slug)}?locale=${locale}`,
      { next: { revalidate: REVALIDATE } },
    );
    if (!res.ok) return null;
    return (await res.json()) as Landing;
  } catch {
    return null;
  }
}

export async function fetchLandings(locale?: Locale): Promise<LandingSummary[]> {
  try {
    const res = await fetch(
      `${BACKEND}/api/public/pages${locale ? `?locale=${locale}` : ""}`,
      { next: { revalidate: REVALIDATE } },
    );
    if (!res.ok) return [];
    return (await res.json()) as LandingSummary[];
  } catch {
    return [];
  }
}

export interface ArticleLink {
  slug: string;
  label: string;
}

/** Published landings WITHOUT a location — the article/guide set, for internal linking.
 *
 * Location landings are already linked from /locations, so the broad-keyword and app-guide pages
 * were the only ones reachable by nothing but the sitemap. Google reports exactly those as
 * "Discovered – currently not indexed": known, but with no internal link earning a crawl. The
 * homepage section + footer row below link them from the site's highest-authority pages.
 *
 * Deduped by slug (fa+en share one URL, as in the sitemap), stable slug order from the API, and the
 * label is the title minus its "— گذرایکس" brand suffix (same trim as the landing's related chips).
 * Locale-agnostic on purpose: a landing serves fa to an en visitor via the backend's fa fallback,
 * so filtering by locale would hide every link in en chrome.
 */
export async function fetchArticleLandings(limit = 8): Promise<ArticleLink[]> {
  const seen = new Set<string>();
  const out: ArticleLink[] = [];
  for (const row of await fetchLandings()) {
    if (row.location_remark || seen.has(row.slug)) continue;
    seen.add(row.slug);
    out.push({ slug: row.slug, label: row.title.split("—")[0].split("|")[0].trim() });
    if (out.length >= limit) break;
  }
  return out;
}
