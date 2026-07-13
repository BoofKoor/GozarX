import type { Metadata } from "next";
import Link from "next/link";
import { getLocale } from "@/lib/server";
import { translator } from "@/lib/i18n";
import { fetchLandings } from "@/lib/landing";
import { breadcrumbLd } from "@/lib/jsonld";
import { JsonLd } from "@/components/JsonLd";
import { LocationsGrid } from "@/components/LocationsGrid";
import { Icon } from "@/components/Icon";

// Locations index — the crawlable hub for every location keyword: a server-rendered SEO intro +
// links to the location landings (internal-link spine), with the live flag grid as a client island.
export async function generateMetadata(): Promise<Metadata> {
  const locale = await getLocale();
  const t = translator(locale);
  return {
    title: `${t("loc_page_title")} — GozarX`,
    description: t("loc_page_sub"),
    alternates: { canonical: "/locations" },
  };
}

export default async function LocationsPage() {
  const locale = await getLocale();
  const t = translator(locale);
  // Location landings for the "popular location guides" cards (graceful []: grid still renders).
  const locLandings = (await fetchLandings(locale)).filter((s) => s.location_remark);

  return (
    <section className="sec locations-page">
      <div className="container">
        <JsonLd
          data={breadcrumbLd([
            { name: t("land_home"), path: "/" },
            { name: t("loc_page_title"), path: "/locations" },
          ])}
        />
        <div className="sec-head">
          <span className="eyebrow">{t("loc_eyebrow")}</span>
          <h1 className="sec-title">{t("loc_page_title")}</h1>
          <p className="sec-sub">{t("loc_page_sub")}</p>
        </div>

        <div className="loc-intro">
          <p>{t("loc_page_p1")}</p>
          <p>{t("loc_page_p2")}</p>
        </div>

        {locLandings.length > 0 && (
          <>
            <h2 className="loc-h2">{t("loc_page_guides")}</h2>
            <div className="loc-cards">
              {locLandings.map((s) => (
                <Link key={s.slug} className="loc-card-link" href={`/l/${s.slug}`}>
                  <b>{s.title.split("—")[0].split("|")[0].trim()}</b>
                  <p>{s.meta_description}</p>
                  <span className="more">
                    {t("loc_go")}
                    <Icon name="arrow" sw={2.2} cls="ic-dir" />
                  </span>
                </Link>
              ))}
            </div>
          </>
        )}

        <h2 className="loc-h2">{t("loc_page_grid")}</h2>
        <LocationsGrid
          locale={locale}
          landings={locLandings.map((s) => ({
            slug: s.slug,
            location_remark: s.location_remark,
          }))}
        />
      </div>
    </section>
  );
}
