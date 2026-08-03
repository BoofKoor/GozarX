import type { Metadata } from "next";
import Link from "next/link";
import { getLocale } from "@/lib/server";
import { translator } from "@/lib/i18n";
import { fetchSiteCopy } from "@/lib/siteCopy";
import { fetchArticleLandings } from "@/lib/landing";

// Self-referencing canonical for the homepage. Set here (not in the root layout) so it applies only
// to `/` — a layout-level canonical would be inherited by every sub-page and wrongly mark them all
// as duplicates of the home page.
export const metadata: Metadata = { alternates: { canonical: "/" } };
import { Icon } from "@/components/Icon";
import { ClaimWidget } from "@/components/ClaimWidget";
import { HomeLocations } from "@/components/home/HomeLocations";
import { HomeMissions } from "@/components/home/HomeMissions";
import { HomeApps } from "@/components/home/HomeApps";
import { HomeStats } from "@/components/home/HomeStats";
import { HomeFaq } from "@/components/home/HomeFaq";

// Homepage — faithful reproduction of docs/website/design/phase-2-homepage.html. Section order:
// hero (copy + live claim widget) → how it works → locations → more volume → apps → stats band →
// FAQ → trust band. Interactive/live sections (widget, locations, apps, FAQ) are client islands;
// the rest is static marketing rendered server-side. No economic numbers are hardcoded.
export default async function HomePage() {
  const locale = await getLocale();
  // Editable hero copy from the admin Texts panel (site_hero_title/sub), with the in-code copy as the
  // fallback. An edited title renders as a single gradient headline; unedited falls back to the
  // two-part design headline. (See lib/siteCopy — degrades to all-null when the backend is absent.)
  const copy = await fetchSiteCopy(locale);
  // The translator takes the panel's overrides as its top layer, so every allowlisted design-copy
  // key on this page is editable without a redeploy. With none set it behaves exactly as before.
  const t = translator(locale, copy.overrides);
  // Article/guide landings, linked from the homepage so they inherit real internal links instead of
  // being sitemap-only orphans (see fetchArticleLandings). Empty list ⇒ the band renders nothing.
  // The cap is deliberately above the seeded count: a low cap silently dropped the tail of the slug
  // ordering (v2rayng-config landed there), leaving exactly the pages this band exists to link.
  const articles = await fetchArticleLandings(24);

  const steps = [
    { t: "how1_t", d: "how1_d", ic: "pin" },
    { t: "how2_t", d: "how2_d", ic: "bolt" },
    { t: "how3_t", d: "how3_d", ic: "download" },
  ] as const;
  return (
    <>
      {/* HERO */}
      <section className="hero" id="hero">
        <div className="container hero-inner">
          <div className="hero-copy">
            <h1>
              {copy.hero_title ? (
                <span className="grad">{copy.hero_title}</span>
              ) : (
                <>
                  {t("hero_h1_a")} <span className="grad">{t("hero_h1_b")}</span>
                </>
              )}
            </h1>
            <p className="sub">{copy.hero_sub ?? t("hero_sub")}</p>
            <div className="trust-row">
              <span className="pill">
                <Icon name="check" sw={2.4} />
                {t("trust1")}
              </span>
              <span className="pill">
                <Icon name="check" sw={2.4} />
                {t("trust2")}
              </span>
              <span className="pill">
                <Icon name="check" sw={2.4} />
                {t("trust3")}
              </span>
              <span className="pill">
                <Icon name="users" sw={2.4} />
                {t("trust4")}
              </span>
            </div>
          </div>
          <div id="hero-widget">
            <ClaimWidget locale={locale} copy={copy.overrides} />
          </div>
        </div>
      </section>

      {/* HOW IT WORKS */}
      <section className="sec" id="how">
        <div className="container">
          <div className="sec-head reveal">
            <span className="eyebrow">{t("how_eyebrow")}</span>
            <h2 className="sec-title">{t("how_title")}</h2>
            <p className="sec-sub">{t("how_sub")}</p>
          </div>
          <div className="steps reveal">
            {steps.map((s) => (
              <div className="step" key={s.t}>
                <div className="num">
                  <Icon name={s.ic} sw={2} />
                </div>
                <h3>{t(s.t)}</h3>
                <p>{t(s.d)}</p>
                <span className="conn" />
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* LOCATIONS (live) */}
      <HomeLocations locale={locale} copy={copy.overrides} />

      {/* MORE VOLUME (live reward amounts) */}
      <HomeMissions locale={locale} copy={copy.overrides} />

      {/* APPS (platform-ordered) */}
      <HomeApps locale={locale} copy={copy.overrides} />

      {/* STATS band (live location count) */}
      <HomeStats locale={locale} />

      {/* FAQ teaser (live accordion) */}
      <HomeFaq locale={locale} copy={copy.overrides} />

      {/* ARTICLES & GUIDES — server-rendered internal links to the /l/* article landings, so the
          anchors are in the raw HTML a crawler sees (no JS) with the page's own keyword as text. */}
      {articles.length > 0 && (
        <section className="sec" id="articles">
          <div className="container">
            <div className="sec-head reveal">
              <span className="eyebrow">{t("art_eyebrow")}</span>
              <h2 className="sec-title">{t("art_title")}</h2>
              <p className="sec-sub">{t("art_sub")}</p>
            </div>
            <div className="art-chips reveal">
              {articles.map((a) => (
                <Link key={a.slug} className="chip" href={`/l/${a.slug}`}>
                  {/* bdi: fa labels stay readable inside en (LTR) chrome — same as landing chips */}
                  <bdi>{a.label}</bdi>
                </Link>
              ))}
            </div>
          </div>
        </section>
      )}

      {/* TRUST band */}
      <section className="sec">
        <div className="container">
          <div className="trust-card reveal">
            <div className="trust-shield">
              <Icon name="shield" sw={2} />
            </div>
            <h2 className="sec-title">{t("trust_title")}</h2>
            <p className="sec-sub" style={{ maxWidth: "40rem", marginInline: "auto" }}>
              {t("trust_sub")}
            </p>
            <div className="trust-badges">
              <span className="tb">
                <Icon name="check" sw={2.6} />
                {t("tb1")}
              </span>
              <span className="tb">
                <Icon name="check" sw={2.6} />
                {t("tb2")}
              </span>
              <span className="tb">
                <Icon name="check" sw={2.6} />
                {t("tb3")}
              </span>
            </div>
            <Link className="link-more" href="/privacy">
              {t("trust_link")}
            </Link>
          </div>
        </div>
      </section>
    </>
  );
}
