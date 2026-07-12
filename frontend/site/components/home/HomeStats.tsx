"use client";

import { useEffect, useState } from "react";
import { type Locale, translator } from "@/lib/i18n";
import { useSite } from "@/lib/useSite";
import { api, type PublicStats } from "@/lib/api";
import { Icon } from "@/components/Icon";

// STATS band — three LIVE, honest figures (no marketing fabrications): configs delivered (a real
// count of claim rows), the active-location count (with a green "online" pulse), and rolling uptime
// (the share of health samples that weren't "down"). All read straight from the public API.
function faDigits(s: string, locale: Locale) {
  return locale === "fa" ? s.replace(/\d/g, (d) => "۰۱۲۳۴۵۶۷۸۹"[+d]) : s;
}

export function HomeStats({ locale }: { locale: Locale }) {
  const t = translator(locale);
  const { locations } = useSite();
  const [stats, setStats] = useState<PublicStats | null>(null);

  useEffect(() => {
    let alive = true;
    api
      .stats()
      .then((s) => alive && setStats(s))
      .catch(() => {});
    return () => {
      alive = false;
    };
  }, []);

  const locCount = locations?.length ?? 0;
  const dash = "—";
  const intl = locale === "fa" ? "fa-IR" : "en-US"; // native grouping (٬) + decimals (٫) for fa
  const pct = locale === "fa" ? "٪" : "%";

  const items = [
    {
      icon: "bolt",
      n: stats ? stats.configs_delivered.toLocaleString(intl) : dash,
      l: t("stat1"),
      live: false,
    },
    { icon: "pin", n: locCount ? faDigits(String(locCount), locale) : dash, l: t("stat2"), live: true },
    {
      icon: "gauge",
      n:
        stats?.uptime_pct != null
          ? stats.uptime_pct.toLocaleString(intl, { maximumFractionDigits: 1 }) + pct
          : dash,
      l: t("stat3"),
      live: false,
    },
  ] as const;

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
