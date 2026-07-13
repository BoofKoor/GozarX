import type { MetadataRoute } from "next";
import { SITE_URL } from "@/lib/site";

// Served at /robots.txt (Next.js metadata route). Let every crawler reach the public marketing pages
// while keeping them off the JSON API and the personalized/utility routes, and point them at the
// sitemap. Kept in sync with sitemap.ts (which lists exactly the indexable pages).
export default function robots(): MetadataRoute.Robots {
  return {
    rules: {
      userAgent: "*",
      allow: "/",
      disallow: ["/api/", "/status", "/offline"],
    },
    sitemap: `${SITE_URL}/sitemap.xml`,
    host: SITE_URL,
  };
}
