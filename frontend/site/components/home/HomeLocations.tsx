"use client";

import { type Locale, translator } from "@/lib/i18n";
import { useSite } from "@/lib/useSite";
import { Flag } from "@/components/widget/pieces";
import { locName } from "@/components/widget/flags";
import { Icon } from "@/components/Icon";

// LOCATIONS teaser — the design's `.locrow` of `.locbig` cards, but fed by the LIVE trial-squad
// locations (never a hardcoded country list). Cards deep-link to the hero widget's picker. Hidden
// entirely when the panel exposes no locations; skeletons while the first load is in flight.
export function HomeLocations({ locale }: { locale: Locale }) {
  const t = translator(locale);
  const { locations, loading } = useSite();
  const list = (locations ?? []).slice(0, 8);
  if (!loading && list.length === 0) return null;

  return (
    <section className="sec" id="locations" style={{ background: "var(--sunken)" }}>
      <div className="container">
        <div className="sec-head reveal">
          <span className="eyebrow">{t("loc_eyebrow")}</span>
          <h2 className="sec-title">{t("loc_title")}</h2>
          <p className="sec-sub">{t("loc_sub")}</p>
        </div>
        <div className="locrow reveal">
          {list.length === 0
            ? Array.from({ length: 8 }).map((_, i) => (
                <div key={i} className="locbig skeleton" style={{ blockSize: 128 }} aria-hidden />
              ))
            : list.map((name) => (
                <a key={name} className="locbig" href="#hero">
                  <span className="flag-wrap" style={{ position: "relative" }}>
                    <Flag name={name} size={52} />
                  </span>
                  <span className="nm">{locName(name)}</span>
                  <span className="go">
                    {t("loc_go")}
                    <Icon name="arrow" sw={2.4} cls="ic-dir" />
                  </span>
                </a>
              ))}
        </div>
        <div className="center-more reveal">
          <a className="link-more" href="#hero">
            {t("loc_all")}
          </a>
        </div>
      </div>
    </section>
  );
}
