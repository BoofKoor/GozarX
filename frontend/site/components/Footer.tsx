import Link from "@/components/Link";
import type { CopyOverrides, Locale } from "@/lib/i18n";
import { translator } from "@/lib/copy";
import type { ArticleLink } from "@/lib/landing";
import { FooterBand, FooterLangs } from "@/components/FooterParts";

// Footer — a CTA-led footer: a "grab today's config" gradient call-to-action band, then brand +
// tagline + three link columns (Product / Resources / Legal), and a bottom bar with a dynamic-year
// copyright + a segmented language toggle. No social or messenger links anywhere (sitewide rule).
// Blog is omitted (the product has no blog). `year` is computed server-side and passed in so it
// hydrates identically (see copyrightYear in lib/i18n). Headings: the band is an h2 and the columns
// h3 — they were h3/h4 on every page, a level below whatever the page's own sections used.
// A server component: only the band (it follows the visitor's state) and the language buttons run
// in the browser (FooterParts); the links are HTML.

export function Footer({
  locale,
  year,
  articles = [],
  copy,
}: {
  locale: Locale;
  year: string;
  /** Article landings, resolved server-side in the root layout (empty ⇒ the row is omitted). */
  articles?: ArticleLink[];
  copy?: CopyOverrides;
}) {
  const t = translator(locale, copy);

  const cols = [
    {
      h: "ftc_product",
      links: [
        { k: "ft_get", href: "/#hero-widget" },
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
        <FooterBand locale={locale} />
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
              <h3>{t(col.h)}</h3>
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
            <Link className="ft-more-all" href="/articles">
              {t("art_all")}
            </Link>
          </nav>
        )}
        <div className="ft-bottom">
          <span>© {year} GozarX — {t("ft_rights")}</span>
          <FooterLangs locale={locale} />
        </div>
      </div>
    </footer>
  );
}
