import type { Metadata, Viewport } from "next";
import { cookies } from "next/headers";
import "./globals.css";
import { DEFAULT_LOCALE, dir, isLocale, type Locale } from "@/lib/i18n";
import { Header } from "@/components/Header";
import { Footer } from "@/components/Footer";
import { PwaRegister } from "@/components/PwaRegister";
import { LogoSymbol } from "@/components/LogoSymbol";
import { RevealObserver } from "@/components/RevealObserver";
import { SiteProvider } from "@/lib/useSite";

type Theme = "light" | "dark";

async function resolve(): Promise<{ locale: Locale; theme: Theme | undefined }> {
  const store = await cookies();
  const rawLocale = store.get("locale")?.value ?? "";
  const locale: Locale = isLocale(rawLocale) ? rawLocale : DEFAULT_LOCALE;
  const rawTheme = store.get("theme")?.value;
  // Only an EXPLICIT choice sets data-theme. With no cookie we leave it unset so the CSS
  // `@media (prefers-color-scheme)` fallback follows the OS (no flash, no client JS needed).
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
  return {
    title: fa ? "گذرایکس — کانفیگ آزمایشی رایگان روزانه" : "GozarX — Free daily trial config",
    description: fa
      ? "هر روز یک کانفیگ آزمایشی رایگان بگیر — بدون ثبت‌نام. حجم روزانه‌ات را با دعوت دوستان بیشتر کن."
      : "Get a free daily trial config — no signup. Grow your daily volume by inviting friends.",
    manifest: "/manifest.webmanifest",
    // Favicon + apple-touch-icon come from the app/icon.svg + app/apple-icon.png file conventions.
  };
}

export default async function RootLayout({ children }: { children: React.ReactNode }) {
  const { locale, theme } = await resolve();
  return (
    <html lang={locale} dir={dir(locale)} data-theme={theme} suppressHydrationWarning>
      <body suppressHydrationWarning>
        <div id="app" data-locale={locale} data-theme={theme} suppressHydrationWarning>
          <LogoSymbol />
          <SiteProvider locale={locale}>
            <Header locale={locale} theme={theme} />
            <main>{children}</main>
            <Footer locale={locale} />
            <RevealObserver />
          </SiteProvider>
        </div>
        <PwaRegister />
      </body>
    </html>
  );
}
