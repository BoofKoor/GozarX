import type { Metadata } from "next";
import Link from "@/components/Link";
import { type LangParams, localeOf } from "@/lib/server";
import { fill } from "@/lib/i18n";
import { translator } from "@/lib/copy";
import { formatPlaces } from "@/lib/format";
import { fetchPublicLocations } from "@/lib/publicData";
import { locLabel } from "@/components/widget/flags";
import { fetchLandings } from "@/lib/landing";
import { breadcrumbLd } from "@/lib/jsonld";
import { JsonLd } from "@/components/JsonLd";
import { LocationsGrid } from "@/components/LocationsGrid";
import { Icon } from "@/components/Icon";
import "@/styles/pages.css";

// Locations index — the crawlable hub for every location keyword: a server-rendered SEO intro +
// links to the location landings (internal-link spine), and the flag grid — server-rendered from the
// same read of the squad's list (C-65), then kept live by the browser.
export async function generateMetadata({ params }: { params: LangParams }): Promise<Metadata> {
  const locale = await localeOf(params);
  const t = translator(locale);
  return {
    title: `${t("loc_page_title")} — GozarX`,
    description: t("loc_page_sub"),
    alternates: { canonical: "/locations" },
  };
}

export default async function LocationsPage({ params }: { params: LangParams }) {
  const locale = await localeOf(params);
  const t = translator(locale);
  // Location landings for the "popular location guides" cards (graceful []: grid still renders).
  const [landings, live] = await Promise.all([fetchLandings(locale), fetchPublicLocations()]);
  const locLandings = landings.filter((s) => s.location_remark);
  // The intro names the places the squad serves right now (C-53) — it claimed "dozens of countries,
  // from Germany and the USA to Turkey and the UAE" whatever the squad held. Without the list the
  // sentence goes rather than guessing.
  const places = live ? formatPlaces(live.map((n) => locLabel(n, locale)), locale, 4) : null;
  const intro = fill(t("loc_page_p1"), { locs: places }) ?? t("loc_page_p1_any");

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
          <p>{intro}</p>
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
          initial={live}
          landings={locLandings.map((s) => ({
            slug: s.slug,
            location_remark: s.location_remark,
          }))}
        />
      </div>
    </section>
  );
}
