"use client";

import { type Locale, faDigits, translator } from "@/lib/i18n";
import { useSite } from "@/lib/useSite";
import type { PublicStats } from "@/lib/api";
import { Icon } from "@/components/Icon";

// STATS band — three LIVE, honest figures (no marketing fabrications): configs delivered (a real
// count of claim rows), the active-location count (with a green "online" pulse), and rolling uptime
// (the share of health samples that weren't "down"). `stats` is the server's /stats, read by the
// page for the hero chip anyway — so the band's figures are in the HTML rather than «—» placeholders
// that a second client-side fetch filled in. A figure the backend could not give is LEFT OUT, not
// printed as «—» (C-38): a dash in a stats band reads as "zero" or "broken", and neither is true.
export function HomeStats({ locale, stats }: { locale: Locale; stats: PublicStats | null }) {
  const t = translator(locale);
  const { locations, loading } = useSite();

  const intl = locale === "fa" ? "fa-IR" : "en-US"; // native grouping (٬) + decimals (٫) for fa
  const pct = locale === "fa" ? "٪" : "%";
  const locCount = locations?.length ?? 0;

  const items = [
    {
      icon: "bolt",
      n: stats ? stats.configs_delivered.toLocaleString(intl) : null,
      l: t("stat1"),
      live: false,
    },
    {
      icon: "pin",
      // the location list is the one figure only the client has: a placeholder while it loads
      // (so the band does not change shape as it arrives), and gone if it never does
      n: locCount ? faDigits(String(locCount), locale) : loading ? "—" : null,
      l: t("stat2"),
      live: true,
    },
    {
      icon: "gauge",
      n:
        stats?.uptime_pct != null
          ? stats.uptime_pct.toLocaleString(intl, { maximumFractionDigits: 1 }) + pct
          : null,
      l: t("stat3"),
      live: false,
    },
  ].filter((s) => s.n !== null);

  if (!items.length) return null;
  return (
    <section className="sec">
      <div className="container">
        <div className="statband reveal">
          {items.map((s) => (
            <div className="c" key={s.l}>
              <span className="tile">
                <Icon name={s.icon} sw={2} />
                {s.live && <span className="onb" aria-hidden />}
              </span>
              <div className="n tnum">{s.n}</div>
              <div className="l">
                {s.live && <span className="pulse" aria-hidden />}
                {s.l}
              </div>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}
