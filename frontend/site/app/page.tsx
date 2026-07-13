import type { Metadata } from "next";
import Link from "next/link";
import { getLocale } from "@/lib/server";
import { translator } from "@/lib/i18n";

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
  const t = translator(locale);

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
              {t("hero_h1_a")} <span className="grad">{t("hero_h1_b")}</span>
            </h1>
            <p className="sub">{t("hero_sub")}</p>
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
            <ClaimWidget locale={locale} />
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
      <HomeLocations locale={locale} />

      {/* MORE VOLUME (live reward amounts) */}
      <HomeMissions locale={locale} />

      {/* APPS (platform-ordered) */}
      <HomeApps locale={locale} />

      {/* STATS band (live location count) */}
      <HomeStats locale={locale} />

      {/* FAQ teaser (live accordion) */}
      <HomeFaq locale={locale} />

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
