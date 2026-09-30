import { type CopyOverrides, type Locale, faDigits } from "@/lib/i18n";
import type { PublicStats } from "@/lib/api";
import { translator } from "@/lib/copy";
import { Icon } from "@/components/Icon";

// STATS band — three LIVE, honest figures (no marketing fabrications): configs delivered (a real
// count of claim rows), the active-location count (with a green "online" pulse), and rolling uptime
// (the share of health samples that weren't "down"). `stats` is the server's /stats, read by the
// page for the hero chip anyway — so the band's figures are in the HTML rather than «—» placeholders
// that a second client-side fetch filled in. A figure the backend could not give is LEFT OUT, not
// printed as «—» (C-38): a dash in a stats band reads as "zero" or "broken", and neither is true.
// A server component: the location count is the squad's list as the page read it (`locations`), so
// all three figures are in the HTML and the band costs no JavaScript.
export function HomeStats({
  locale,
  stats,
  locations,
  copy,
}: {
  locale: Locale;
  stats: PublicStats | null;
  locations: string[] | null;
  copy?: CopyOverrides;
}) {
  const t = translator(locale, copy);
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
      n: locCount ? faDigits(String(locCount), locale) : null,
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
