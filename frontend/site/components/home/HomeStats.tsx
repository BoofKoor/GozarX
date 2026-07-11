"use client";

import { type Locale, translator } from "@/lib/i18n";
import { useSite } from "@/lib/useSite";

// STATS band — the design's dark `.band` with three figures. The "active locations" figure is the
// LIVE trial-squad count (never a hardcoded 8); the other two are the design's marketing figures.
function faDigits(s: string, locale: Locale) {
  return locale === "fa" ? s.replace(/\d/g, (d) => "۰۱۲۳۴۵۶۷۸۹"[+d]) : s;
}

export function HomeStats({ locale }: { locale: Locale }) {
  const t = translator(locale);
  const { locations } = useSite();
  const locCount = locations?.length ?? 0;
  const stats = [
    { n: locale === "fa" ? "۲٫۴M" : "2.4M", l: "stat1" },
    { n: locCount ? faDigits(String(locCount), locale) : "—", l: "stat2" },
    { n: locale === "fa" ? "۹۹٫۹٪" : "99.9%", l: "stat3" },
  ];
  return (
    <section className="sec">
      <div className="container">
        <div className="band reveal">
          <div className="band-inner">
            {stats.map((s) => (
              <div className="stat" key={s.l}>
                <div className="n tnum">{s.n}</div>
                <div className="l">{t(s.l)}</div>
              </div>
            ))}
          </div>
        </div>
      </div>
    </section>
  );
}
