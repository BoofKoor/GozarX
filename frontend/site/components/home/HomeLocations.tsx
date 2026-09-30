"use client";

import Link from "next/link";
import { type CopyOverrides, type Locale, faDigits, fill, translator } from "@/lib/i18n";
import { formatPlaces } from "@/lib/format";
import { useSite } from "@/lib/useSite";
import { flagCC, locLabel, locName } from "@/components/widget/flags";
import { Icon } from "@/components/Icon";

// LOCATIONS teaser — a single compact card: a dotted world map (decorative "global presence"), a
// LIVE pill with the REAL active-location count, and a flag strip of the live trial-squad locations.
// Replaces the old tall 8-card grid. Data (count + flags) is live; the map is illustrative. Hidden
// when the panel exposes no locations. Each flag PICKS its location in the claim widget above
// (`/?loc=`, V-11) — they were pictures of choices that could not be chosen — and from 900px the
// card runs map-beside-flags across the row instead of a 520px card in the middle of 1180.
const SHOWN = 5;

export function HomeLocations({ locale, copy }: { locale: Locale; copy?: CopyOverrides }) {
  const t = translator(locale, copy);
  const { locations, loading } = useSite();
  const list = locations ?? [];
  const total = list.length;
  if (!loading && total === 0) return null;

  const skeleton = total === 0; // first load in flight
  // `{locs}` is the squad's own list, in the reader's language (C-53): the sentence used to name
  // Ukraine, Germany and the USA whether or not the squad served any of them. An override without
  // the token renders as written; until the list arrives the line keeps its height, empty.
  const sub = fill(t("loc_sub"), {
    locs: formatPlaces(
      list.map((n) => locLabel(n, locale)),
      locale,
    ),
  });
  const shown = list.slice(0, SHOWN);
  const more = Math.max(0, total - SHOWN);

  return (
    <section className="sec" id="locations" style={{ background: "var(--sunken)" }}>
      <div className="container">
        <div className="sec-head reveal">
          <span className="eyebrow">{t("loc_eyebrow")}</span>
          <h2 className="sec-title">{t("loc_title")}</h2>
          {sub ? (
            <p className="sec-sub">{sub}</p>
          ) : (
            <p className="sec-sub" aria-hidden>
              {"\u00a0"}
            </p>
          )}
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

          <div className="locside">
            <div className="locdiv" />

            <div className="flagstrip">
              {skeleton
                ? Array.from({ length: SHOWN }).map((_, i) => (
                    <span key={i} className="fbig skeleton" aria-hidden />
                  ))
                : shown.map((name) => {
                    const cc = flagCC(name);
                    // the link carries the MATCHING key (the remark); the reader gets their language
                    const label = locLabel(name, locale);
                    return (
                      <Link
                        key={name}
                        className="fbig-link"
                        href={`/?loc=${encodeURIComponent(locName(name))}#hero-widget`}
                        aria-label={label}
                        title={label}
                      >
                        {cc ? (
                          <img className="fbig" src={`/flags/${cc}.svg`} alt="" loading="lazy" />
                        ) : (
                          <span className="fbig fb-fallback" aria-hidden>
                            {label.slice(0, 2).toUpperCase()}
                          </span>
                        )}
                      </Link>
                    );
                  })}
              {more > 0 && (
                <Link className="flagmore" href="/locations" aria-label={t("loc_all")}>
                  +{faDigits(String(more), locale)}
                </Link>
              )}
            </div>

            <p className="loccap">{t("loc_worldwide")}</p>
            <Link className="loccta" href="/locations">
              {t("loc_all")}
              <Icon name="arrow" sw={2.2} cls="ic-dir" />
            </Link>
          </div>
        </div>
      </div>
    </section>
  );
}
