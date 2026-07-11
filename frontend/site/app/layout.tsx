import type { Metadata, Viewport } from "next";
import { cookies } from "next/headers";
import "./globals.css";
import { DEFAULT_LOCALE, dir, isLocale, type Locale } from "@/lib/i18n";
import { Header } from "@/components/Header";
import { Footer } from "@/components/Footer";
import { PwaRegister } from "@/components/PwaRegister";

async function resolve(): Promise<{ locale: Locale; theme: "light" | "dark" }> {
  const store = await cookies();
  const rawLocale = store.get("locale")?.value ?? "";
  const locale: Locale = isLocale(rawLocale) ? rawLocale : DEFAULT_LOCALE;
  const rawTheme = store.get("theme")?.value;
  const theme = rawTheme === "dark" ? "dark" : "light";
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

// Runs before paint: if the visitor has no explicit theme cookie, honor prefers-color-scheme so the
// first frame isn't the wrong theme. suppressHydrationWarning covers the attribute it may flip.
const THEME_SCRIPT = `(function(){try{if(!document.cookie.includes("theme=")){var d=matchMedia("(prefers-color-scheme: dark)").matches?"dark":"light";document.documentElement.setAttribute("data-theme",d);var a=document.getElementById("app");if(a)a.setAttribute("data-theme",d);}}catch(e){}})();`;

export default async function RootLayout({ children }: { children: React.ReactNode }) {
  const { locale, theme } = await resolve();
  return (
    <html lang={locale} dir={dir(locale)} data-theme={theme} suppressHydrationWarning>
      <head>
        <script dangerouslySetInnerHTML={{ __html: THEME_SCRIPT }} />
      </head>
      <body suppressHydrationWarning>
        <div id="app" data-locale={locale} data-theme={theme} suppressHydrationWarning>
          <Header locale={locale} theme={theme} />
          <main>{children}</main>
          <Footer locale={locale} />
        </div>
        <PwaRegister />
      </body>
    </html>
  );
}
