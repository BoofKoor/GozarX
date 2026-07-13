import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";
import { getLocale } from "@/lib/server";
import { translator } from "@/lib/i18n";
import { fetchLanding, fetchLandings } from "@/lib/landing";
import { breadcrumbLd } from "@/lib/jsonld";
import { JsonLd } from "@/components/JsonLd";
import { ClaimWidget } from "@/components/ClaimWidget";

// SEO keyword landing — one URL per admin-authored `site_landing_pages` row («کانفیگ آلمان»,
// «آیپی آمریکا», …). Server-rendered so crawlers get the full article + metadata without JS; the
// claim widget rides along as the usual client island with the row's location pre-selected.
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
  return {
    title: row.title,
    description: row.meta_description,
    alternates: { canonical: `/l/${slug}` },
    openGraph: { title: row.title, description: row.meta_description, url: `/l/${slug}` },
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
          <span aria-hidden>‹</span>
          {/* bdi: the crumb label is row-locale text inside chrome that may run the other way */}
          <bdi>{row.heading ?? row.title}</bdi>
        </nav>

        {/* h1 carries the row's own lang/dir like the body: in the en-chrome + fa-fallback case a
            Persian heading inside an LTR page would otherwise render visually scrambled. */}
        <h1 lang={row.locale} dir={rtl ? "rtl" : "ltr"}>
          {row.heading ?? row.title}
        </h1>

        {/* Body is TRUSTED admin-authored HTML: rows come only from the JWT-gated admin CRUD
            (backend admin/landing.py documents the contract) — no user input ever reaches it. */}
        <div
          className="landing-body"
          lang={row.locale}
          dir={rtl ? "rtl" : "ltr"}
          dangerouslySetInnerHTML={{ __html: row.body }}
        />

        <div className="landing-widget" id="get">
          <ClaimWidget locale={locale} preselect={row.location_remark ?? undefined} />
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
    </section>
  );
}
