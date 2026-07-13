"use client";

import Link from "next/link";
import { type Locale, translator } from "@/lib/i18n";
import { useSite } from "@/lib/useSite";
import { locName } from "@/components/widget/flags";
import { Flag } from "@/components/widget/pieces";

// Live location grid for /locations — the full flag list from the trial squad (client island; the
// SEO copy around it is server-rendered). A cell whose location has a matching keyword landing
// (by location_remark / display name) deep-links there; the rest jump to the home claim widget.
export function LocationsGrid({
  locale,
  landings,
}: {
  locale: Locale;
  landings: { slug: string; location_remark: string | null }[];
}) {
  const t = translator(locale);
  const { locations, loading } = useSite();
  const list = locations ?? [];

  const landingFor = (loc: string): string | null => {
    const want = locName(loc).toLowerCase();
    const hit = landings.find(
      (l) =>
        l.location_remark &&
        (l.location_remark === loc || locName(l.location_remark).toLowerCase() === want),
    );
    return hit ? `/l/${hit.slug}` : null;
  };

  if (!loading && list.length === 0) return null;
  const skeleton = list.length === 0;

  return (
    <div className="locgrid">
      {skeleton
        ? Array.from({ length: 12 }).map((_, i) => (
            <span key={i} className="loccell skeleton" aria-hidden />
          ))
        : list.map((loc) => {
            const href = landingFor(loc) ?? "/#hero";
            return (
              <Link key={loc} className="loccell" href={href}>
                <Flag name={loc} size={34} />
                <span className="ln">{locName(loc)}</span>
                <span className="lg">{t("loc_go")}</span>
              </Link>
            );
          })}
    </div>
  );
}
