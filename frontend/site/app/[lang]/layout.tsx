import type { Metadata, Viewport } from "next";
import "@/styles/tokens.css";
import "@/styles/base.css";
import { LOCALES } from "@/lib/i18n";
import { type LangParams, localeOf } from "@/lib/server";
import { GOOGLE_SITE_VERIFICATION, SITE_URL } from "@/lib/site";
import { SiteDocument } from "@/components/SiteDocument";
import { fetchSiteCopy } from "@/lib/siteCopy";

// The root layout of both language trees (`proxy.ts` picks one per request). Nothing here reads the
// request — no cookies, no headers — so every page under it is static: rendered once, then served
// from the cache and rebuilt in the background every five minutes (C-61).
//
// Rendered at the FIRST REQUEST, not at build: the image is built with no backend to read, so a
// build-time page would bake the fallbacks in (no FAQ rows, no landings, no stats) and serve them
// until the first revalidation — to whoever came first, a crawler included. An empty list here
// means "none at build, each on its first visit"; `LOCALES` still bounds what `[lang]` can be.
export function generateStaticParams(): { lang: (typeof LOCALES)[number] }[] {
  return [];
}

// How long a rendered page is served before it is rebuilt in the background: the same five minutes
// every backend read on the site revalidates at (site copy, landings, FAQ, /config, /stats), so a
// panel edit still reaches the site within ~5 minutes — now without a render per visit.
export const revalidate = 300;

export const viewport: Viewport = {
  themeColor: "#2563EB",
  width: "device-width",
  initialScale: 1,
};

export async function generateMetadata({ params }: { params: LangParams }): Promise<Metadata> {
  const locale = await localeOf(params);
  const fa = locale === "fa";
  // Home title/description target the head keyword cluster («کانفیگ رایگان V2Ray») + the no-signup
  // USP; sub-pages override both with their own generateMetadata. These are the FALLBACKS — the
  // admin can override them from the Texts panel (site_meta_title/description), fetched below and
  // applied when set, so homepage SEO copy is tunable without a redeploy.
  const fallbackTitle = fa
    ? "کانفیگ رایگان V2Ray روزانه، بدون ثبت‌نام | گذرایکس GozarX"
    : "GozarX — Free daily V2Ray config, no signup";
  const fallbackDescription = fa
    ? "هر روز یک کانفیگ رایگان و اختصاصی V2Ray/VLESS بگیر — بدون ثبت‌نام و شماره. لوکیشن دلخواه را انتخاب کن و حجم روزانه‌ات را با دعوت دوستان بیشتر کن."
    : "Get a fresh personal V2Ray/VLESS config every day — no signup, no phone. Pick your location and grow your daily volume by inviting friends.";
  const copy = await fetchSiteCopy(locale);
  const title = copy.meta_title ?? fallbackTitle;
  const description = copy.meta_description ?? fallbackDescription;
  return {
    // Base for all relative URLs below (canonical, OG, Twitter) so Google receives absolute links.
    metadataBase: new URL(SITE_URL),
    applicationName: "GozarX",
    title,
    description,
    // The installed app's name and description in the page's own language (C-68). Both manifests
    // share one `id`, so installing from either language is the same app.
    manifest: fa ? "/manifest.webmanifest" : "/manifest-en.webmanifest",
    keywords: fa
      ? [
          "کانفیگ رایگان",
          "کانفیگ رایگان v2ray",
          "کانفیگ vless رایگان",
          "فیلترشکن رایگان بدون ثبت نام",
          "کانفیگ روزانه",
          "گذرایکس",
          "GozarX",
        ]
      : ["free config", "free v2ray config", "vless config", "daily config", "GozarX"],
    // Public pages should index + be followed; give Google's bot the roomiest snippet/preview.
    robots: {
      index: true,
      follow: true,
      googleBot: {
        index: true,
        follow: true,
        "max-image-preview": "large",
        "max-snippet": -1,
        "max-video-preview": -1,
      },
    },
    // Shared OG/Twitter chrome (image, siteName, type, locale, card). Deliberately NO title/
    // description here: Next fills og:title/og:description (and twitter's) from each page's own
    // resolved title/description. Setting them here would pin the HOME copy onto every sub-page's
    // and every landing's social card (they inherit this object when they don't override it).
    // The image is the 1200×630 card (C-66) — the 512px square icon was cropped to a sliver by every
    // large-card preview; a location landing swaps in its own, with that country's flag.
    openGraph: {
      type: "website",
      siteName: "GozarX",
      locale: fa ? "fa_IR" : "en_US",
      images: [{ url: "/og/site.png", width: 1200, height: 630, alt: "GozarX" }],
    },
    twitter: {
      card: "summary_large_image",
      images: ["/og/site.png"],
    },
    // Search Console "HTML tag" verification — only emitted when the token env var is set (else
    // verify via DNS/Cloudflare, no tag needed).
    verification: GOOGLE_SITE_VERIFICATION ? { google: GOOGLE_SITE_VERIFICATION } : undefined,
    // Favicon + apple-touch-icon come from the app/icon.svg + app/apple-icon.png file conventions.
  };
}

export default async function RootLayout({
  children,
  params,
}: {
  children: React.ReactNode;
  params: LangParams;
}) {
  return <SiteDocument locale={await localeOf(params)}>{children}</SiteDocument>;
}
