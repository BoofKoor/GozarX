import type { Metadata } from "next";
import Link from "next/link";
import { getLocale } from "@/lib/server";
import { translator } from "@/lib/i18n";
import { fetchLandings, type LandingSummary } from "@/lib/landing";
import { breadcrumbLd } from "@/lib/jsonld";
import { JsonLd } from "@/components/JsonLd";
import { Icon } from "@/components/Icon";

// Articles index — every article/guide landing (the ones WITHOUT a location; those have /locations)
// as a card. The homepage features four and the footer five, both with "all articles" pointing here,
// so the rest keep an internal link instead of existing only in the sitemap (V-08). Server-rendered:
// the anchors are in the HTML a crawler reads.
export async function generateMetadata(): Promise<Metadata> {
  const t = translator(await getLocale());
  return {
    title: `${t("art_page_title")} — GozarX`,
    description: t("art_page_sub"),
    alternates: { canonical: "/articles" },
  };
}

export default async function ArticlesPage() {
  const locale = await getLocale();
  const t = translator(locale);
  // One card per slug, in the visitor's language where the article has it — a landing serves its fa
  // row to an en visitor (the backend's fallback), so an en-only filter would empty the page.
  const bySlug = new Map<string, LandingSummary>();
  for (const row of await fetchLandings()) {
    if (row.location_remark) continue;
    const prev = bySlug.get(row.slug);
    if (!prev || (prev.locale !== locale && row.locale === locale)) bySlug.set(row.slug, row);
  }
  const articles = [...bySlug.values()];

  return (
    <section className="sec articles-page">
      <div className="container">
        <JsonLd
          data={breadcrumbLd([
            { name: t("land_home"), path: "/" },
            { name: t("art_page_title"), path: "/articles" },
          ])}
        />
        <div className="sec-head">
          <span className="eyebrow">{t("art_eyebrow")}</span>
          <h1 className="sec-title">{t("art_page_title")}</h1>
          <p className="sec-sub">{t("art_page_sub")}</p>
        </div>
        {articles.length > 0 ? (
          <div className="art-cards three">
            {articles.map((a) => (
              <Link key={a.slug} className="art-card" href={`/l/${a.slug}`}>
                {/* the row carries its own language: a Persian article inside en chrome */}
                <b lang={a.locale} dir={a.locale === "fa" ? "rtl" : "ltr"}>
                  {a.title.split("—")[0].split("|")[0].trim()}
                </b>
                <p lang={a.locale} dir={a.locale === "fa" ? "rtl" : "ltr"}>
                  {a.meta_description}
                </p>
                <span className="more">
                  {t("art_read")}
                  <Icon name="arrow" sw={2.2} cls="ic-dir" />
                </span>
              </Link>
            ))}
          </div>
        ) : (
          <p className="empty">{t("art_empty")}</p>
        )}
      </div>
    </section>
  );
}
