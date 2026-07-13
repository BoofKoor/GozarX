import type { MetadataRoute } from "next";
import { PLATFORMS } from "@/lib/content";
import { fetchLandings } from "@/lib/landing";
import { SITE_URL } from "@/lib/site";

// Regenerate hourly at runtime so admin-authored landings appear without a redeploy. At BUILD time
// (inside Docker, no backend up) fetchLandings fails gracefully to [] and the static list below is
// emitted — the first revalidation after boot fills the landings in.
export const revalidate = 3600;

type Freq = NonNullable<MetadataRoute.Sitemap[number]["changeFrequency"]>;

// Served at /sitemap.xml (Next.js metadata route). Lists the public, indexable pages: the marketing
// pages, one guide page per platform, the locations index, and every published keyword landing
// (/l/{slug}). The personalized /status view and the /offline PWA fallback are deliberately
// excluded (and also disallowed in robots.ts).
export default async function sitemap(): Promise<MetadataRoute.Sitemap> {
  const now = new Date();
  const pages: { path: string; priority: number; changeFrequency: Freq }[] = [
    { path: "/", priority: 1, changeFrequency: "daily" },
    { path: "/guides", priority: 0.8, changeFrequency: "monthly" },
    ...PLATFORMS.map((p) => ({
      path: `/guides/${p}`,
      priority: 0.7,
      changeFrequency: "monthly" as Freq,
    })),
    { path: "/locations", priority: 0.8, changeFrequency: "weekly" },
    { path: "/about", priority: 0.6, changeFrequency: "monthly" },
    { path: "/faq", priority: 0.6, changeFrequency: "monthly" },
    { path: "/contact", priority: 0.5, changeFrequency: "monthly" },
    { path: "/privacy", priority: 0.3, changeFrequency: "yearly" },
    { path: "/terms", priority: 0.3, changeFrequency: "yearly" },
  ];
  const statics: MetadataRoute.Sitemap = pages.map(({ path, priority, changeFrequency }) => ({
    url: `${SITE_URL}${path}`,
    lastModified: now,
    changeFrequency,
    priority,
  }));

  // fa+en rows share one URL (locale is cookie-switched) — dedupe by slug, newest updated_at wins.
  const bySlug = new Map<string, string | null>();
  for (const row of await fetchLandings()) {
    const prev = bySlug.get(row.slug);
    if (prev === undefined || (row.updated_at ?? "") > (prev ?? "")) {
      bySlug.set(row.slug, row.updated_at);
    }
  }
  const landings: MetadataRoute.Sitemap = [...bySlug.entries()].map(([slug, updatedAt]) => ({
    url: `${SITE_URL}/l/${slug}`,
    lastModified: updatedAt ? new Date(updatedAt) : now,
    changeFrequency: "weekly",
    priority: 0.7,
  }));

  return [...statics, ...landings];
}
