import type { MetadataRoute } from "next";
import { SITE_URL } from "@/lib/site";

// Served at /robots.txt (Next.js metadata route). Let every crawler reach the public marketing pages
// while keeping them off the JSON API and the personalized/utility routes, and point them at the
// sitemap. Kept in sync with sitemap.ts (which lists exactly the indexable pages).
//
// `/api/` stays closed although Google's renderer honours this file for a page's own requests too:
// `/status` mints a device per cookieless call, so a crawler let in would fill `site_devices` and
// the visitor figures. The claim widget draws its picker from the page's server read instead
// (ClaimWidget `initial`), which is what kept it from rendering as an error card for Google.
//
// `/?loc=<remark>` is the homepage with a location picked — the flag strip and every /locations
// cell without a landing link one. To a crawler each is one more URL to fetch only to find the
// homepage again (its canonical says so after the fetch): ~20 of them on a 32-page site, spent from
// the same crawl the landings wait on.
export default function robots(): MetadataRoute.Robots {
  return {
    rules: {
      userAgent: "*",
      allow: "/",
      disallow: ["/api/", "/status", "/offline", "/*?loc="],
    },
    sitemap: `${SITE_URL}/sitemap.xml`,
    // No `host`: a Yandex-only directive (since retired) that every other crawler ignores or flags
    // as invalid (C-66) — the canonical origin is already in the sitemap URL and every page's tags.
  };
}
