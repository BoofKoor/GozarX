"use client";

import { type Locale, translator } from "@/lib/i18n";
import { useSite } from "@/lib/useSite";
import { Icon } from "@/components/Icon";

// STATS band — three LIVE, honest figures (no marketing fabrications): the active-location count
// (with a green "online" pulse), the free daily volume, and each config's validity — all read
// straight from the public API (locations, daily_limit, trial_hours). Never hardcoded.
function faDigits(s: string, locale: Locale) {
  return locale === "fa" ? s.replace(/\d/g, (d) => "۰۱۲۳۴۵۶۷۸۹"[+d]) : s;
}

// Split a human amount like "700.0 MB" into a clean figure ("700") + unit ("MB"); drops a trailing ".0".
function splitAmount(v: string | undefined): { n: string; u: string } {
  if (!v) return { n: "—", u: "" };
  const m = /^([\d.,٫٬]+)\s*(.*)$/.exec(v.trim());
  if (!m) return { n: v, u: "" };
  return { n: m[1].replace(/[.٫]0+$/, ""), u: m[2] };
}

export function HomeStats({ locale }: { locale: Locale }) {
  const t = translator(locale);
  const { status, locations } = useSite();

  const locCount = locations?.length ?? 0;
  const vol = splitAmount(status?.daily_limit);
  const hours = status?.trial_hours;

  const stats = [
    { icon: "pin", n: locCount ? faDigits(String(locCount), locale) : "—", u: "", l: t("stat2"), live: true },
    { icon: "bolt", n: faDigits(vol.n, locale), u: vol.u, l: t("stat_daily"), live: false },
    {
      icon: "clock",
      n: hours ? faDigits(String(hours), locale) : "—",
      u: hours ? t("stat_hours") : "",
      l: t("stat_validity"),
      live: false,
    },
  ] as const;

  return (
    <section className="sec">
      <div className="container">
        <div className="statband reveal">
          {stats.map((s) => (
            <div className="c" key={s.l}>
              <span className="tile">
                <Icon name={s.icon} sw={2} />
                {s.live && <span className="onb" aria-hidden />}
              </span>
              <div className="n tnum">
                {s.n}
                {s.u && <span className="u"> {s.u}</span>}
              </div>
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
