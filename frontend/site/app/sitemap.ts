import type { MetadataRoute } from "next";
import { PLATFORMS } from "@/lib/content";
import { fetchLandingsOrThrow } from "@/lib/landing";
import { SITE_URL } from "@/lib/site";

// Rendered on every request, never prerendered. The build has no backend, so the prerendered copy
// listed the 14 fixed pages and NO landing — and that copy was what a fresh server handed out: after
// every deploy or restart for five minutes, and then once more as the stale copy a regeneration
// serves first — to whoever asked first, which may well have been Googlebot. The landing list still
// comes through the 5-minute fetch cache, so this costs the backend nothing extra.
export const dynamic = "force-dynamic";

type Freq = NonNullable<MetadataRoute.Sitemap[number]["changeFrequency"]>;

// Served at /sitemap.xml (Next.js metadata route). Lists the public, indexable pages: the marketing
// pages, one guide page per platform, the locations and articles indexes, and every published
// keyword landing (/l/{slug}). The personalized /status view and the /offline PWA fallback are
// deliberately excluded (and also disallowed in robots.ts).
//
// With the backend unreachable this FAILS rather than answering the fixed pages alone: a sitemap is
// a claim about what exists, a 5xx makes Google keep the copy it has and come back, and a short one
// tells it every landing is gone. `lastmod` is only ever a real date — a landing's `updated_at`; the
// fixed pages carry none, because stamping them "now" on every render (as this did) is a date Google
// learns to ignore, and then it ignores the landings' real ones too.
export default async function sitemap(): Promise<MetadataRoute.Sitemap> {
  const pages: { path: string; priority: number; changeFrequency: Freq }[] = [
    { path: "/", priority: 1, changeFrequency: "daily" },
    { path: "/guides", priority: 0.8, changeFrequency: "monthly" },
    ...PLATFORMS.map((p) => ({
      path: `/guides/${p}`,
      priority: 0.7,
      changeFrequency: "monthly" as Freq,
    })),
    { path: "/locations", priority: 0.8, changeFrequency: "weekly" },
    { path: "/articles", priority: 0.7, changeFrequency: "weekly" },
    { path: "/about", priority: 0.6, changeFrequency: "monthly" },
    { path: "/faq", priority: 0.6, changeFrequency: "monthly" },
    { path: "/contact", priority: 0.5, changeFrequency: "monthly" },
    { path: "/privacy", priority: 0.3, changeFrequency: "yearly" },
    { path: "/terms", priority: 0.3, changeFrequency: "yearly" },
  ];
  const statics: MetadataRoute.Sitemap = pages.map(({ path, priority, changeFrequency }) => ({
    url: `${SITE_URL}${path}`,
    changeFrequency,
    priority,
  }));

  // fa+en rows share one URL (locale is cookie-switched) — dedupe by slug, newest updated_at wins.
  const bySlug = new Map<string, string | null>();
  for (const row of await fetchLandingsOrThrow()) {
    const prev = bySlug.get(row.slug);
    if (prev === undefined || (row.updated_at ?? "") > (prev ?? "")) {
      bySlug.set(row.slug, row.updated_at);
    }
  }
  const landings: MetadataRoute.Sitemap = [...bySlug.entries()].map(([slug, updatedAt]) => ({
    url: `${SITE_URL}/l/${slug}`,
    ...(updatedAt ? { lastModified: new Date(updatedAt) } : {}),
    changeFrequency: "weekly",
    priority: 0.7,
  }));

  return [...statics, ...landings];
}
