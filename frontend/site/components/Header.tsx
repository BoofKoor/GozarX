"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { type Locale, translator } from "@/lib/i18n";

function setCookie(name: string, value: string) {
  document.cookie = `${name}=${value}; path=/; max-age=${400 * 24 * 3600}; samesite=lax`;
}

const NAV: { href: string; key: string }[] = [
  { href: "/guides", key: "nav_guides" },
  { href: "/faq", key: "nav_faq" },
  { href: "/contact", key: "nav_contact" },
];

// Clean header — brand + nav + "My status" + burger. Language is auto-detected and theme follows
// the device by default; both are changed from the mobile sheet, the footer, or the status-page
// settings — deliberately NOT in the header bar (an fa searcher already implies the fa locale).
export function Header({ locale, theme }: { locale: Locale; theme?: "light" | "dark" }) {
  const router = useRouter();
  const t = translator(locale);
  const [sheet, setSheet] = useState(false);
  const [themeState, setThemeState] = useState<string>(theme ?? "");

  // Let Escape close the mobile nav sheet (it's a modal surface).
  useEffect(() => {
    if (!sheet) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") setSheet(false);
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [sheet]);

  function switchLocale(next: Locale) {
    if (next === locale) return;
    setCookie("locale", next);
    const html = document.documentElement;
    html.setAttribute("lang", next);
    html.setAttribute("dir", next === "fa" ? "rtl" : "ltr");
    document.getElementById("app")?.setAttribute("data-locale", next);
    setSheet(false);
    router.refresh();
  }

  function setTheme(next: "light" | "dark") {
    setCookie("theme", next);
    document.documentElement.setAttribute("data-theme", next);
    document.getElementById("app")?.setAttribute("data-theme", next);
    setThemeState(next);
  }

  return (
    <>
      <header className="hd">
        <div className="container hd-row">
          <Link className="brandmark" href="/" aria-label="GozarX">
            <svg className="logo" viewBox="0 0 639 508" role="img" aria-label="GozarX">
              <use href="#gz-logo" />
            </svg>
            GozarX
          </Link>
          <nav className="mainnav">
            {NAV.map((n) => (
              <Link key={n.href} className="navlink" href={n.href}>
                {t(n.key)}
              </Link>
            ))}
          </nav>
          <div className="hd-spacer" />
          <div className="hd-ctrls">
            <Link className="btn secondary status-btn" href="/status">
              {t("nav_status")}
            </Link>
            <button
              className="icon-only burger"
              aria-label="menu"
              aria-expanded={sheet}
              onClick={() => setSheet(true)}
            >
              <svg className="ic" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round">
                <path d="M4 7h16M4 12h16M4 17h16" />
              </svg>
            </button>
          </div>
        </div>
      </header>

      {/* mobile sheet — nav + the language/theme controls (kept out of the header bar) */}
      <div className={`sheet-ov${sheet ? " open" : ""}`} onClick={() => setSheet(false)} />
      <div className={`sheet${sheet ? " open" : ""}`} role="dialog" aria-modal="true" aria-label={t("nav.home")}>
        <div className="sheet-handle" />
        <nav id="sheetnav">
          {[{ href: "/", key: "nav.home" }, ...NAV, { href: "/status", key: "nav_status" }].map(
            (n) => (
              <Link key={n.href} className="navlink" href={n.href} onClick={() => setSheet(false)}>
                {t(n.key)}
              </Link>
            ),
          )}
        </nav>
        <div className="sheet-sep" />
        <div className="sheet-controls">
          <div className="seg" role="group" aria-label={t("set_lang")}>
            <button aria-pressed={locale === "fa"} onClick={() => switchLocale("fa")}>
              فارسی
            </button>
            <button aria-pressed={locale === "en"} onClick={() => switchLocale("en")}>
              English
            </button>
          </div>
          <div className="seg" role="group" aria-label={t("set_theme")}>
            <button aria-pressed={themeState === "light"} onClick={() => setTheme("light")}>
              {t("set_theme_l")}
            </button>
            <button aria-pressed={themeState === "dark"} onClick={() => setTheme("dark")}>
              {t("set_theme_d")}
            </button>
          </div>
        </div>
      </div>
    </>
  );
}
