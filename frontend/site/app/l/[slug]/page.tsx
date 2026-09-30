import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";
import { getLocale } from "@/lib/server";
import { fill, translator } from "@/lib/i18n";
import { fetchLanding, fetchLandings } from "@/lib/landing";
import { breadcrumbLd } from "@/lib/jsonld";
import { JsonLd } from "@/components/JsonLd";
import { Icon } from "@/components/Icon";
import { ClaimWidget } from "@/components/ClaimWidget";
import { StickyCta } from "@/components/StickyCta";
import { locLabel } from "@/components/widget/flags";

// SEO keyword landing — one URL per admin-authored `site_landing_pages` row («کانفیگ آلمان»,
// «آیپی آمریکا», …). Server-rendered so crawlers get the full article + metadata without JS; the
// claim widget rides along as the usual client island with the row's location pre-selected.
// The widget comes FIRST, under the H1 (C-26): a visitor searching «کانفیگ آلمان» wants the config,
// and after the article it sat ~1,000px down a phone — while every seeded body tells the reader it
// is «بالای همین صفحه». The article follows, and a closing band sends a finished reader back up.
// Request-time dynamic (getLocale reads cookies), so nothing here ever fetches during `next build`.
//
// hreflang is intentionally absent: one URL serves both locales by cookie, and same-URL alternates
// are invalid — crawlers (no cookie) get fa, the target keyword market.

export async function generateMetadata({
  params,
}: {
  params: Promise<{ slug: string }>;
}): Promise<Metadata> {
  const { slug } = await params;
  const row = await fetchLanding(slug, await getLocale());
  if (!row) return { title: "GozarX" }; // page 404s anyway
  const rtl = row.locale === "fa";
  return {
    title: row.title,
    description: row.meta_description,
    alternates: { canonical: `/l/${slug}` },
    // Setting openGraph REPLACES the layout's object, so re-carry the shared chrome (type/siteName/
    // locale/image) — otherwise the landing's social card loses its image and the twitter card
    // (which would inherit the home title) disagrees with it.
    openGraph: {
      type: "website",
      siteName: "GozarX",
      locale: rtl ? "fa_IR" : "en_US",
      title: row.title,
      description: row.meta_description,
      url: `/l/${slug}`,
      images: [{ url: "/icons/icon-512.png", width: 512, height: 512, alt: "GozarX" }],
    },
  };
}

export default async function LandingPage({ params }: { params: Promise<{ slug: string }> }) {
  const { slug } = await params;
  const locale = await getLocale();
  const t = translator(locale);
  // Same (slug, locale) as generateMetadata — Next memoizes the fetch, so this is one backend hit.
  const row = await fetchLanding(slug, locale);
  if (!row) notFound();

  // Related landings for internal linking (same locale the row was served in; drop self, cap 6).
  const related = (await fetchLandings(row.locale as "fa" | "en"))
    .filter((s) => s.slug !== slug)
    .slice(0, 6);

  // The served row may be the fa fallback inside en chrome — the article carries its own lang/dir.
  const rtl = row.locale === "fa";
  // A location landing names its location in the widget and the closing band; an article landing
  // keeps the widget's own title.
  const loc = row.location_remark ? locLabel(row.location_remark, locale) : null;
  const widgetTitle = loc ? (fill(t("land_w_title"), { loc }) ?? undefined) : undefined;
  const ctaHead = (loc && fill(t("land_cta_h"), { loc })) || t("land_cta_h_any");

  return (
    <section className="sec landing-page">
      <div className="container" style={{ maxWidth: 720 }}>
        <JsonLd
          data={breadcrumbLd([
            { name: t("land_home"), path: "/" },
            { name: row.title, path: `/l/${slug}` },
          ])}
        />
        <nav className="crumbs" aria-label="breadcrumb">
          <Link href="/">{t("land_home")}</Link>
          {/* a mirrored icon, not a "‹" glyph — bidi mirrors that one in RTL, so it pointed back at
              «خانه» in both languages and read as a parenthesis in Persian */}
          <Icon name="chevr" sw={2.2} cls="ic-dir crumb-sep" />
          {/* bdi: the crumb label is row-locale text inside chrome that may run the other way */}
          <bdi>{row.heading ?? row.title}</bdi>
        </nav>

        {/* h1 carries the row's own lang/dir like the body: in the en-chrome + fa-fallback case a
            Persian heading inside an LTR page would otherwise render visually scrambled. */}
        <h1 lang={row.locale} dir={rtl ? "rtl" : "ltr"}>
          {row.heading ?? row.title}
        </h1>

        <div className="landing-widget" id="get">
          <ClaimWidget
            locale={locale}
            preselect={row.location_remark ?? undefined}
            title={widgetTitle}
          />
        </div>

        {/* Admin-authored HTML, SANITISED by the backend on the way out (services/article_html):
            this origin is the admin panel's too, so a handler in a pasted body would run where the
            admin tokens live. Only bare article tags and vetted links survive. */}
        <div
          className="landing-body"
          lang={row.locale}
          dir={rtl ? "rtl" : "ltr"}
          dangerouslySetInnerHTML={{ __html: row.body }}
        />

        {/* the reader who finished the article is a long way below the widget */}
        <div className="land-cta">
          <div className="land-cta-t">
            <h2>{ctaHead}</h2>
            <p>{t("land_cta_d")}</p>
          </div>
          <a className="ft-cta-btn" href="#get">
            <Icon name="bolt" sw={2.2} />
            {t("sticky_get")}
          </a>
        </div>

        {related.length > 0 && (
          <div className="landing-related">
            <h2>{t("land_related")}</h2>
            <div className="chips">
              {related.map((s) => (
                <Link key={s.slug} className="chip" href={`/l/${s.slug}`}>
                  <bdi>{s.title.split("—")[0].split("|")[0].trim()}</bdi>
                </Link>
              ))}
            </div>
          </div>
        )}
      </div>
      <StickyCta locale={locale} target=".landing-widget" />
    </section>
  );
}
