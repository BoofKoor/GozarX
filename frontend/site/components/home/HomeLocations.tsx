"use client";

import { type Locale, faDigits, translator } from "@/lib/i18n";
import { useSite } from "@/lib/useSite";
import { flagCC, locName } from "@/components/widget/flags";
import { Icon } from "@/components/Icon";

// LOCATIONS teaser — a single compact card: a dotted world map (decorative "global presence"), a
// LIVE pill with the REAL active-location count, and a flag strip of the live trial-squad locations.
// Replaces the old tall 8-card grid. Data (count + flags) is live; the map is illustrative. Hidden
// when the panel exposes no locations.
const SHOWN = 5;

export function HomeLocations({ locale }: { locale: Locale }) {
  const t = translator(locale);
  const { locations, loading } = useSite();
  const list = locations ?? [];
  const total = list.length;
  if (!loading && total === 0) return null;

  const skeleton = total === 0; // first load in flight
  const shown = list.slice(0, SHOWN);
  const more = Math.max(0, total - SHOWN);

  return (
    <section className="sec" id="locations" style={{ background: "var(--sunken)" }}>
      <div className="container">
        <div className="sec-head reveal">
          <span className="eyebrow">{t("loc_eyebrow")}</span>
          <h2 className="sec-title">{t("loc_title")}</h2>
          <p className="sec-sub">{t("loc_sub")}</p>
        </div>

        <div className="loccard reveal">
          <div className="locframe">
            {!skeleton && (
              <span className="livepill">
                <span className="livedot" aria-hidden />
                <b>{faDigits(String(total), locale)}</b> {t("loc_active")}
              </span>
            )}
            <img className="worldmap" src="/map-world.webp" alt="" width={640} height={382} />
          </div>

          <div className="locdiv" />

          <div className="flagstrip">
            {skeleton
              ? Array.from({ length: SHOWN }).map((_, i) => (
                  <span key={i} className="fbig skeleton" aria-hidden />
                ))
              : shown.map((name) => {
                  const cc = flagCC(name);
                  return cc ? (
                    <img key={name} className="fbig" src={`/flags/${cc}.svg`} alt={locName(name)} loading="lazy" />
                  ) : (
                    <span key={name} className="fbig fb-fallback" aria-hidden>
                      {locName(name).slice(0, 2).toUpperCase()}
                    </span>
                  );
                })}
            {more > 0 && <span className="flagmore">+{faDigits(String(more), locale)}</span>}
          </div>

          <p className="loccap">{t("loc_worldwide")}</p>
          <a className="loccta" href="/locations">
            {t("loc_all")}
            <Icon name="arrow" sw={2.2} cls="ic-dir" />
          </a>
        </div>
      </div>
    </section>
  );
}
