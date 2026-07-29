import type { Metadata, Viewport } from "next";
import { cookies } from "next/headers";
import "./globals.css";
import { copyrightYear, dir, type Locale } from "@/lib/i18n";
import { getLocale } from "@/lib/server";
import { GOOGLE_SITE_VERIFICATION, SITE_URL } from "@/lib/site";
import { organizationLd, webSiteLd } from "@/lib/jsonld";
import { JsonLd } from "@/components/JsonLd";
import { Header } from "@/components/Header";
import { Footer } from "@/components/Footer";
import { PwaRegister } from "@/components/PwaRegister";
import { LogoSymbol } from "@/components/LogoSymbol";
import { RevealObserver } from "@/components/RevealObserver";
import { SiteProvider } from "@/lib/useSite";

type Theme = "light" | "dark";

async function resolve(): Promise<{ locale: Locale; theme: Theme | undefined }> {
  // Locale: cookie → Accept-Language → fa (auto-detected; changed from settings, not the header).
  const locale = await getLocale();
  const rawTheme = (await cookies()).get("theme")?.value;
  // Only an EXPLICIT choice sets data-theme. With no cookie we leave it unset so the CSS
  // `@media (prefers-color-scheme)` fallback follows the device OS (no flash, no client JS needed).
  const theme: Theme | undefined = rawTheme === "dark" ? "dark" : rawTheme === "light" ? "light" : undefined;
  return { locale, theme };
}

export const viewport: Viewport = {
  themeColor: "#2563EB",
  width: "device-width",
  initialScale: 1,
};

export async function generateMetadata(): Promise<Metadata> {
  const { locale } = await resolve();
  const fa = locale === "fa";
  // Home title/description target the head keyword cluster («کانفیگ رایگان V2Ray») + the no-signup
  // USP; sub-pages override both with their own generateMetadata.
  const title = fa
    ? "کانفیگ رایگان V2Ray روزانه، بدون ثبت‌نام | گذرایکس GozarX"
    : "GozarX — Free daily V2Ray config, no signup";
  const description = fa
    ? "هر روز یک کانفیگ رایگان و اختصاصی V2Ray/VLESS بگیر — بدون ثبت‌نام و شماره. لوکیشن دلخواه را انتخاب کن و حجم روزانه‌ات را با دعوت دوستان بیشتر کن."
    : "Get a fresh personal V2Ray/VLESS config every day — no signup, no phone. Pick your location and grow your daily volume by inviting friends.";
  return {
    // Base for all relative URLs below (canonical, OG, Twitter) so Google receives absolute links.
    metadataBase: new URL(SITE_URL),
    applicationName: "GozarX",
    title,
    description,
    manifest: "/manifest.webmanifest",
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
    openGraph: {
      type: "website",
      siteName: "GozarX",
      locale: fa ? "fa_IR" : "en_US",
      images: [{ url: "/icons/icon-512.png", width: 512, height: 512, alt: "GozarX" }],
    },
    twitter: {
      card: "summary",
      images: ["/icons/icon-512.png"],
    },
    // Search Console "HTML tag" verification — only emitted when the token env var is set (else
    // verify via DNS/Cloudflare, no tag needed).
    verification: GOOGLE_SITE_VERIFICATION ? { google: GOOGLE_SITE_VERIFICATION } : undefined,
    // Favicon + apple-touch-icon come from the app/icon.svg + app/apple-icon.png file conventions.
  };
}

export default async function RootLayout({ children }: { children: React.ReactNode }) {
  const { locale, theme } = await resolve();
  const fontFile = locale === "fa" ? "/fonts/YekanBakh-VF.woff2" : "/fonts/Inter-Variable-latin.woff2";
  return (
    <html lang={locale} dir={dir(locale)} data-theme={theme} suppressHydrationWarning>
      <body suppressHydrationWarning>
        {/* React 19 hoists these into <head>: preload the primary font (faster LCP text paint) and
            emit the sitewide Organization + WebSite JSON-LD. */}
        <link rel="preload" href={fontFile} as="font" type="font/woff2" crossOrigin="anonymous" />
        <JsonLd data={organizationLd()} />
        <JsonLd data={webSiteLd(locale)} />
        <div id="app" data-locale={locale} data-theme={theme} suppressHydrationWarning>
          <LogoSymbol />
          <SiteProvider locale={locale}>
            <Header locale={locale} theme={theme} />
            <main>{children}</main>
            <Footer locale={locale} year={copyrightYear(locale)} />
            <RevealObserver />
          </SiteProvider>
        </div>
        <PwaRegister />
      </body>
    </html>
  );
}
