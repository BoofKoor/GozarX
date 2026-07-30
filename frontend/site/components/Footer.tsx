"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { type Locale, translator } from "@/lib/i18n";
import type { ArticleLink } from "@/lib/landing";
import { Icon } from "@/components/Icon";

// Footer — a CTA-led footer: a "grab today's config" gradient call-to-action band, then brand +
// tagline + three link columns (Product / Resources / Legal), and a bottom bar with a dynamic-year
// copyright + a segmented language toggle. No social or messenger links anywhere (sitewide rule).
// Blog is omitted (the product has no blog). `year` is computed server-side and passed in so it
// hydrates identically (see copyrightYear in lib/i18n).
function setCookie(name: string, value: string) {
  document.cookie = `${name}=${value}; path=/; max-age=${400 * 24 * 3600}; samesite=lax`;
}

export function Footer({
  locale,
  year,
  articles = [],
}: {
  locale: Locale;
  year: string;
  /** Article landings, resolved server-side in the root layout (empty ⇒ the row is omitted). */
  articles?: ArticleLink[];
}) {
  const t = translator(locale);
  const router = useRouter();

  function switchLocale(next: Locale) {
    if (next === locale) return;
    setCookie("locale", next);
    const html = document.documentElement;
    html.setAttribute("lang", next);
    html.setAttribute("dir", next === "fa" ? "rtl" : "ltr");
    document.getElementById("app")?.setAttribute("data-locale", next);
    router.refresh();
  }

  const cols = [
    {
      h: "ftc_product",
      links: [
        { k: "ft_get", href: "/#hero" },
        { k: "ft_loc", href: "/locations" },
        { k: "ft_rewards", href: "/#rewards" },
        { k: "ft_status", href: "/status" },
      ],
    },
    {
      h: "ftc_resources",
      links: [
        { k: "ft_guides", href: "/guides" },
        { k: "ft_faq", href: "/faq" },
        { k: "ft_about", href: "/about" },
      ],
    },
    {
      h: "ftc_legal",
      links: [
        { k: "ft_terms", href: "/terms" },
        { k: "ft_privacy", href: "/privacy" },
        { k: "ft_contact", href: "/contact" },
      ],
    },
  ] as const;

  return (
    <footer className="ft">
      <div className="container">
        <div className="ft-cta">
          <div className="ft-cta-t">
            <h3>{t("ft_cta_h")}</h3>
            <p>{t("ft_cta_d")}</p>
          </div>
          <Link className="ft-cta-btn" href="/#hero">
            {t("ft_cta_btn")}
            <Icon name="arrow" sw={2.2} cls="ic-dir" />
          </Link>
        </div>
        <div className="ft-grid">
          <div className="ft-brand">
            <Link className="brandmark" href="/" aria-label="GozarX">
              <svg className="logo" viewBox="0 0 639 508" role="img" aria-label="GozarX">
                <use href="#gz-logo" />
              </svg>
              GozarX
            </Link>
            <p>{t("ft_tag")}</p>
          </div>
          {cols.map((col) => (
            <div className="ft-col" key={col.h}>
              <h4>{t(col.h)}</h4>
              {col.links.map((l) => (
                <Link key={l.k} href={l.href}>
                  {t(l.k)}
                </Link>
              ))}
            </div>
          ))}
        </div>
        {/* Article landings as one wrapping row (not a 5th grid column — the grid is exactly full at
            1.7fr 1fr 1fr 1fr and long Persian titles would crush it). Sitewide, so every page passes
            internal link equity to pages that would otherwise only exist in the sitemap. */}
        {articles.length > 0 && (
          <nav className="ft-more" aria-label={t("ft_articles")}>
            <span className="ft-more-h">{t("ft_articles")}</span>
            {articles.map((a) => (
              <Link key={a.slug} href={`/l/${a.slug}`}>
                <bdi>{a.label}</bdi>
              </Link>
            ))}
          </nav>
        )}
        <div className="ft-bottom">
          <span>© {year} GozarX — {t("ft_rights")}</span>
          <div className="ft-langs" role="group" aria-label="language">
            <button aria-pressed={locale === "fa"} onClick={() => switchLocale("fa")}>
              فارسی
            </button>
            <button aria-pressed={locale === "en"} onClick={() => switchLocale("en")}>
              English
            </button>
          </div>
        </div>
      </div>
    </footer>
  );
}
