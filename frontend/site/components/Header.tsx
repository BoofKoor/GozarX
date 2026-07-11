"use client";

import { useState } from "react";
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

export function Header({ locale }: { locale: Locale; theme?: "light" | "dark" }) {
  const router = useRouter();
  const t = translator(locale);
  const [sheet, setSheet] = useState(false);

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

  function toggleTheme() {
    const app = document.getElementById("app");
    const current =
      app?.getAttribute("data-theme") ??
      (window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light");
    const next = current === "dark" ? "light" : "dark";
    setCookie("theme", next);
    document.documentElement.setAttribute("data-theme", next);
    app?.setAttribute("data-theme", next);
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
              <Link key={n.href} href={n.href}>
                {t(n.key)}
              </Link>
            ))}
          </nav>
          <div className="hd-spacer" />
          <div className="hd-ctrls">
            <div className="seg" role="group" aria-label="language">
              <button aria-pressed={locale === "fa"} onClick={() => switchLocale("fa")}>
                فا
              </button>
              <button aria-pressed={locale === "en"} onClick={() => switchLocale("en")}>
                EN
              </button>
            </div>
            <button className="icon-only th-btn" onClick={toggleTheme} aria-label={t("theme.toggle")}>
              <MoonIcon />
              <SunIcon />
            </button>
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

      {/* mobile sheet */}
      <div className={`sheet-ov${sheet ? " show" : ""}`} onClick={() => setSheet(false)} />
      <div className={`sheet${sheet ? " show" : ""}`}>
        <div className="sheet-handle" />
        <nav id="sheetnav">
          {[{ href: "/", key: "nav.home" }, ...NAV, { href: "/status", key: "nav_status" }].map(
            (n) => (
              <Link key={n.href} href={n.href} onClick={() => setSheet(false)}>
                {t(n.key)}
              </Link>
            ),
          )}
        </nav>
        <div className="sheet-sep" />
        <div className="sheet-controls">
          <div className="seg" role="group">
            <button aria-pressed={locale === "fa"} onClick={() => switchLocale("fa")}>
              فارسی
            </button>
            <button aria-pressed={locale === "en"} onClick={() => switchLocale("en")}>
              English
            </button>
          </div>
        </div>
      </div>
    </>
  );
}

function MoonIcon() {
  return (
    <svg className="ic moon" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M21 12.8A9 9 0 1 1 11.2 3a7 7 0 0 0 9.8 9.8Z" />
    </svg>
  );
}
function SunIcon() {
  return (
    <svg className="ic sun" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <circle cx="12" cy="12" r="4.5" />
      <path d="M12 2v2M12 20v2M2 12h2M20 12h2M5 5l1.5 1.5M17.5 17.5 19 19M19 5l-1.5 1.5M6.5 17.5 5 19" />
    </svg>
  );
}
