"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { type Locale, translator } from "@/lib/i18n";
import { Icon } from "@/components/Icon";

function setCookie(name: string, value: string) {
  document.cookie = `${name}=${value}; path=/; max-age=${400 * 24 * 3600}; samesite=lax`;
}

const NAV: { href: string; key: string }[] = [
  { href: "/locations", key: "nav_loc" },
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

  // Reflect the EFFECTIVE theme in the toggle. An explicit choice sets `data-theme`; with no cookie
  // the page follows the OS via `prefers-color-scheme` and `data-theme` is unset — so read the media
  // query in that case (otherwise the switch wrongly shows light while a dark OS renders dark). Stay
  // in sync if the OS theme changes while no explicit choice is active.
  useEffect(() => {
    const mq = window.matchMedia("(prefers-color-scheme: dark)");
    const sync = () => {
      const attr = document.getElementById("app")?.getAttribute("data-theme");
      setThemeState(attr === "light" || attr === "dark" ? attr : mq.matches ? "dark" : "light");
    };
    sync();
    mq.addEventListener("change", sync);
    return () => mq.removeEventListener("change", sync);
  }, []);

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
            {/* desktop-only theme + language controls (mobile has them in the burger sheet) */}
            <div className="hd-lang" role="group" aria-label={t("set_lang")}>
              <button aria-pressed={locale === "fa"} onClick={() => switchLocale("fa")}>
                فا
              </button>
              <button aria-pressed={locale === "en"} onClick={() => switchLocale("en")}>
                EN
              </button>
            </div>
            <ThemeSwitch
              className="hd-theme"
              state={themeState}
              label={t("set_theme")}
              onToggle={() => setTheme(themeState === "dark" ? "light" : "dark")}
            />
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
          <ThemeSwitch
            state={themeState}
            label={t("set_theme")}
            onToggle={() => setTheme(themeState === "dark" ? "light" : "dark")}
          />
        </div>
      </div>
    </>
  );
}

// The icon-only sliding sun⇄moon theme switch — shared by the header (desktop) and the mobile sheet.
function ThemeSwitch({
  state,
  label,
  onToggle,
  className,
}: {
  state: string;
  label: string;
  onToggle: () => void;
  className?: string;
}) {
  return (
    <button
      className={`theme-switch${className ? ` ${className}` : ""}${state === "dark" ? " is-dark" : ""}`}
      type="button"
      role="switch"
      aria-checked={state === "dark"}
      aria-label={label}
      onClick={onToggle}
    >
      <span className="thumb" aria-hidden />
      <span className="slot sun" aria-hidden>
        <Icon name="sun" sw={2} />
      </span>
      <span className="slot moon" aria-hidden>
        <Icon name="moon" sw={2} />
      </span>
    </button>
  );
}
