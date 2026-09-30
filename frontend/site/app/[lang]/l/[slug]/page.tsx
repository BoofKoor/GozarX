import type { Metadata } from "next";
import Link from "@/components/Link";
import { notFound } from "next/navigation";
import { localeOf } from "@/lib/server";
import { fill } from "@/lib/i18n";
import { translator } from "@/lib/copy";
import { fetchLanding, fetchLandings } from "@/lib/landing";
import { breadcrumbLd } from "@/lib/jsonld";
import { JsonLd } from "@/components/JsonLd";
import { Icon } from "@/components/Icon";
import { ClaimWidget } from "@/components/ClaimWidget";
import { StickyCta } from "@/components/StickyCta";
import { locLabel } from "@/components/widget/flags";
import "@/styles/pages.css";

// SEO keyword landing — one URL per admin-authored `site_landing_pages` row («کانفیگ آلمان»,
// «آیپی آمریکا», …). Server-rendered so crawlers get the full article + metadata without JS; the
// claim widget rides along as the usual client island with the row's location pre-selected.
// The widget comes FIRST, under the H1 (C-26): a visitor searching «کانفیگ آلمان» wants the config,
// and after the article it sat ~1,000px down a phone — while every seeded body tells the reader it
// is «بالای همین صفحه». The article follows, and a closing band sends a finished reader back up.
// Static (C-61): rendered at a slug's first visit, then served from the cache and rebuilt every five
// minutes; nothing is prerendered at build, which has no backend to read.
//
// hreflang is intentionally absent (decision D3: SEO is Persian-only): one URL serves both locales,
// picked by `proxy.ts`, and same-URL alternates are invalid — crawlers (no cookie) get fa.

// Landings are rows the operator adds in the panel at any time, so none is known at build: each is
// rendered at its first visit and cached from then on (`dynamicParams` stays on). An unknown slug
// 404s — and is cached as one for the same five minutes, which a panel-created slug can outlive.
export function generateStaticParams(): { slug: string }[] {
  return [];
}

export async function generateMetadata({
  params,
}: {
  params: Promise<{ lang: string; slug: string }>;
}): Promise<Metadata> {
  const { slug } = await params;
  const row = await fetchLanding(slug, await localeOf(params));
  if (!row) return { title: "GozarX" }; // page 404s anyway
  const rtl = row.locale === "fa";
  // A location landing's card carries that country's flag (C-66); an article shares the site's.
  const image = row.location_remark ? `/og/${slug}.png` : "/og/site.png";
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
      images: [{ url: image, width: 1200, height: 630, alt: row.title }],
    },
    twitter: { card: "summary_large_image", title: row.title, description: row.meta_description, images: [image] },
  };
}

export default async function LandingPage({ params }: { params: Promise<{ lang: string; slug: string }> }) {
  const { slug } = await params;
  const locale = await localeOf(params);
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
        <nav className="crumbs" aria-label={t("crumbs")}>
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
