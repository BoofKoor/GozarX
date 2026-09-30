"use client";

import { useCallback, useRef, useState } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { type Locale, translator } from "@/lib/i18n";
import { useLocaleSwitch } from "@/lib/prefs";
import { useFocusTrap } from "@/lib/useFocusTrap";
import { Icon } from "@/components/Icon";
import { ThemeChoice } from "@/components/ThemeChoice";

const NAV: { href: string; key: string; icon: string }[] = [
  { href: "/locations", key: "nav_loc", icon: "pin" },
  { href: "/guides", key: "nav_guides", icon: "book" },
  { href: "/faq", key: "nav_faq", icon: "help" },
  { href: "/contact", key: "nav_contact", icon: "mail" },
];
// The phone menu leads with the visitor's own page and ends with Home — the logo already goes
// there, so as the FIRST item it pushed everything else down for the one link nobody opens it for.
const SHEET_NAV = [
  { href: "/status", key: "nav_status", icon: "user" },
  ...NAV,
  { href: "/", key: "nav.home", icon: "home" },
];

// Pages that carry a claim widget of their own don't need the header's shortcut to one.
function hasOwnWidget(pathname: string): boolean {
  return pathname === "/" || pathname === "/status" || pathname.startsWith("/l/");
}

// A link is "here" on its own page and on anything under it (/guides → /guides/android) — marked for
// sighted readers (.active) and screen readers (aria-current) alike.
function isCurrent(pathname: string, href: string): boolean {
  return href === "/" ? pathname === "/" : pathname === href || pathname.startsWith(`${href}/`);
}

// Clean header — brand + nav + "My status" + burger. Language is auto-detected and theme follows
// the device by default; both can be changed from the header's desktop controls, the mobile sheet,
// the footer, or the status-page settings — all through `lib/prefs`, so they cannot disagree.
export function Header({ locale, theme }: { locale: Locale; theme?: "light" | "dark" }) {
  const pathname = usePathname() ?? "/";
  const t = translator(locale);
  const [sheet, setSheet] = useState(false);
  const switchLocale = useLocaleSwitch(locale);
  const sheetRef = useRef<HTMLDivElement>(null);
  const closeSheet = useCallback(() => setSheet(false), []);
  // The phone menu is a modal surface and keeps the whole contract (C-24): focus moves into it and
  // back to the burger, Tab stays inside, Esc closes, and the page behind does not scroll — before,
  // Tab walked out of the open menu into the claim widget under it.
  useFocusTrap(sheetRef, closeSheet, sheet);
  // Every page is a path to the widget (C-23): the header's shortcut on desktop, the top of the
  // menu on a phone. A landing and the account page carry a widget of their own.
  const ctaHref = pathname.startsWith("/l/")
    ? "#get"
    : pathname === "/status"
      ? "#claim"
      : "/#hero-widget";
  const serverTheme = theme ?? "system";

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
              <Link
                key={n.href}
                className={`navlink${isCurrent(pathname, n.href) ? " active" : ""}`}
                aria-current={isCurrent(pathname, n.href) ? "page" : undefined}
                href={n.href}
              >
                {t(n.key)}
              </Link>
            ))}
          </nav>
          <div className="hd-spacer" />
          <div className="hd-ctrls">
            {!hasOwnWidget(pathname) && (
              <Link className="hd-cta" href={ctaHref}>
                <Icon name="bolt" sw={2.2} />
                {t("cta_get")}
              </Link>
            )}
            {/* desktop-only theme + language controls (mobile has them in the burger sheet) */}
            <div className="hd-lang" role="group" aria-label={t("set_lang")}>
              <button aria-pressed={locale === "fa"} onClick={() => switchLocale("fa")}>
                فا
              </button>
              <button aria-pressed={locale === "en"} onClick={() => switchLocale("en")}>
                EN
              </button>
            </div>
            <ThemeChoice
              locale={locale}
              serverChoice={serverTheme}
              variant="icons"
              className="hd-theme"
            />
            {/* brand-tint chip + person icon — the account cards' tile language. On mobile the
                label hides and the chip collapses to the burger's exact footprint (CSS). */}
            <Link
              className="acct-btn status-btn"
              href="/status"
              aria-label={t("nav_status")}
              aria-current={isCurrent(pathname, "/status") ? "page" : undefined}
            >
              <Icon name="user" sw={2} />
              <span className="acct-lbl">{t("nav_status")}</span>
            </Link>
            <button
              className="icon-only burger"
              aria-label={t("menu_open")}
              aria-expanded={sheet}
              aria-controls="site-menu"
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
      <div
        id="site-menu"
        ref={sheetRef}
        className={`sheet${sheet ? " open" : ""}`}
        role="dialog"
        aria-modal="true"
        aria-label={t("menu_title")}
        tabIndex={-1}
      >
        <div className="sheet-top">
          <div className="sheet-handle" aria-hidden />
          <button type="button" className="icon-only sheet-close" aria-label={t("menu_close")} onClick={closeSheet}>
            <Icon name="x" sw={2.2} />
          </button>
        </div>
        <Link className="btn cta sheet-cta" href={ctaHref} onClick={closeSheet}>
          <Icon name="bolt" sw={2.2} />
          {t("cta_get")}
        </Link>
        <nav id="sheetnav">
          {SHEET_NAV.map((n) => (
            <Link
              key={n.href}
              className={`navlink${isCurrent(pathname, n.href) ? " active" : ""}`}
              aria-current={isCurrent(pathname, n.href) ? "page" : undefined}
              href={n.href}
              onClick={closeSheet}
            >
              <Icon name={n.icon} sw={2} />
              {t(n.key)}
            </Link>
          ))}
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
          <ThemeChoice locale={locale} serverChoice={serverTheme} variant="icons" />
        </div>
      </div>
    </>
  );
}
