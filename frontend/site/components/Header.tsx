"use client";

import { useRouter } from "next/navigation";
import Link from "next/link";
import { type Locale, translator } from "@/lib/i18n";

function setCookie(name: string, value: string) {
  document.cookie = `${name}=${value}; path=/; max-age=${400 * 24 * 3600}; samesite=lax`;
}

export function Header({ locale, theme }: { locale: Locale; theme: "light" | "dark" }) {
  const router = useRouter();
  const t = translator(locale);

  function switchLocale(next: Locale) {
    if (next === locale) return;
    setCookie("locale", next);
    const html = document.documentElement;
    html.setAttribute("lang", next);
    html.setAttribute("dir", next === "fa" ? "rtl" : "ltr");
    document.getElementById("app")?.setAttribute("data-locale", next);
    router.refresh();
  }

  function toggleTheme() {
    const next = (document.getElementById("app")?.getAttribute("data-theme") ?? theme) === "dark" ? "light" : "dark";
    setCookie("theme", next);
    document.documentElement.setAttribute("data-theme", next);
    document.getElementById("app")?.setAttribute("data-theme", next);
  }

  return (
    <header className="site-header">
      <div className="container nav">
        <Link href="/" className="brand" aria-label="GozarX">
          <LogoMark />
          <span>GozarX</span>
        </Link>
        <nav className="nav-actions" style={{ marginInlineStart: 8 }} aria-label="Primary">
          <Link href="/" className="navlink hide-sm">
            {t("nav.home")}
          </Link>
          <Link href="/status" className="navlink">
            {t("nav.status")}
          </Link>
          <Link href="/contact" className="navlink hide-sm">
            {t("nav.contact")}
          </Link>
        </nav>
        <div className="nav-spacer" />
        <div className="nav-actions">
          <div className="seg" role="group" aria-label="Language">
            <button aria-pressed={locale === "fa"} onClick={() => switchLocale("fa")}>
              فا
            </button>
            <button aria-pressed={locale === "en"} onClick={() => switchLocale("en")}>
              EN
            </button>
          </div>
          <button className="icon-btn" onClick={toggleTheme} aria-label={t("theme.toggle")}>
            <ThemeIcon />
          </button>
          <Link href="/status" className="btn btn-primary hide-sm">
            {t("nav.getConfig")}
          </Link>
        </div>
      </div>
    </header>
  );
}

function LogoMark() {
  return (
    <svg viewBox="0 0 32 32" fill="none" aria-hidden>
      <rect width="32" height="32" rx="9" fill="var(--logo-accent)" />
      <path d="M9 20.5c0-4 3-7 7-7 2.2 0 4 1 5 2.6" stroke="#fff" strokeWidth="2.4" strokeLinecap="round" />
      <circle cx="16" cy="16" r="2.4" fill="#fff" />
    </svg>
  );
}

function ThemeIcon() {
  return (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden>
      <path d="M21 12.8A9 9 0 1 1 11.2 3a7 7 0 0 0 9.8 9.8Z" strokeLinejoin="round" />
    </svg>
  );
}
