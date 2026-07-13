// JSON-LD builders (schema.org). Only the types Google still uses in 2026: Organization + WebSite
// sitewide and BreadcrumbList per page — FAQPage/HowTo rich results were retired (2023–2025), so we
// deliberately don't emit them. All URLs are absolute via SITE_URL.

import type { Locale } from "@/lib/i18n";
import { SITE_URL } from "@/lib/site";

export function organizationLd(): Record<string, unknown> {
  return {
    "@context": "https://schema.org",
    "@type": "Organization",
    name: "GozarX",
    alternateName: "گذرایکس",
    url: SITE_URL,
    logo: `${SITE_URL}/icons/icon-512.png`,
  };
}

export function webSiteLd(locale: Locale): Record<string, unknown> {
  return {
    "@context": "https://schema.org",
    "@type": "WebSite",
    name: "GozarX",
    url: SITE_URL,
    inLanguage: locale === "fa" ? "fa-IR" : "en",
  };
}

export function breadcrumbLd(items: { name: string; path: string }[]): Record<string, unknown> {
  return {
    "@context": "https://schema.org",
    "@type": "BreadcrumbList",
    itemListElement: items.map((it, i) => ({
      "@type": "ListItem",
      position: i + 1,
      name: it.name,
      item: `${SITE_URL}${it.path}`,
    })),
  };
}
