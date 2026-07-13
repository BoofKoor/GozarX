import type { MetadataRoute } from "next";
import { PLATFORMS } from "@/lib/content";
import { SITE_URL } from "@/lib/site";

type Freq = NonNullable<MetadataRoute.Sitemap[number]["changeFrequency"]>;

// Served at /sitemap.xml (Next.js metadata route). Lists the public, indexable pages: the marketing
// pages plus one guide page per platform. The personalized /status view and the /offline PWA
// fallback are deliberately excluded (and also disallowed in robots.ts). `lastModified` is the build
// time, which is the correct freshness signal for these statically-built pages.
export default function sitemap(): MetadataRoute.Sitemap {
  const now = new Date();
  const pages: { path: string; priority: number; changeFrequency: Freq }[] = [
    { path: "/", priority: 1, changeFrequency: "daily" },
    { path: "/guides", priority: 0.8, changeFrequency: "monthly" },
    ...PLATFORMS.map((p) => ({
      path: `/guides/${p}`,
      priority: 0.7,
      changeFrequency: "monthly" as Freq,
    })),
    { path: "/about", priority: 0.6, changeFrequency: "monthly" },
    { path: "/faq", priority: 0.6, changeFrequency: "monthly" },
    { path: "/contact", priority: 0.5, changeFrequency: "monthly" },
    { path: "/privacy", priority: 0.3, changeFrequency: "yearly" },
    { path: "/terms", priority: 0.3, changeFrequency: "yearly" },
  ];
  return pages.map(({ path, priority, changeFrequency }) => ({
    url: `${SITE_URL}${path}`,
    lastModified: now,
    changeFrequency,
    priority,
  }));
}
