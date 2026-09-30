"use client";

import Link from "@/components/Link";
import { type Locale } from "@/lib/i18n";
import { useT } from "@/lib/useT";
import { useSite } from "@/lib/useSite";
import { locLabel, locName } from "@/components/widget/flags";
import { Flag } from "@/components/widget/Flag";

// Live location grid for /locations — the full flag list from the trial squad. The server's read of
// the list (`initial`) is in the HTML, so a crawler sees every location and its link (C-65): the grid
// used to exist only after the browser's own fetch. That fetch still runs and replaces it — the
// device's own view of the list — but the first paint no longer waits on it. A cell whose location
// has a matching keyword landing
// (by location_remark / display name) deep-links there; the rest open the home claim widget WITH
// that location picked (`/?loc=`, C-27) — they used to land on "#hero" with the popular one chosen,
// so a visitor who tapped هلند was offered آلمان.
export function LocationsGrid({
  locale,
  landings,
  initial,
}: {
  locale: Locale;
  landings: { slug: string; location_remark: string | null }[];
  /** The squad's list as the server read it (null when it could not). */
  initial: string[] | null;
}) {
  const t = useT();
  const { locations, loading } = useSite();
  const list = locations ?? initial ?? [];

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
  // the first screen's cells load their flags at once; the rest wait until scrolled near (C-63)
  const EAGER = 8;

  return (
    <div className="locgrid">
      {skeleton
        ? Array.from({ length: 12 }).map((_, i) => (
            <span key={i} className="loccell skeleton" aria-hidden />
          ))
        : list.map((loc, i) => {
            const href =
              landingFor(loc) ?? `/?loc=${encodeURIComponent(locName(loc))}#hero-widget`;
            // No inline "get" label: the whole cell is the link, and long Persian names
            // (آذربایجان، کره جنوبی…) need the full width to render untruncated.
            return (
              <Link key={loc} className="loccell" href={href} title={t("loc_go")}>
                <Flag name={loc} size={34} eager={i < EAGER} />
                <span className="ln">{locLabel(loc, locale)}</span>
              </Link>
            );
          })}
    </div>
  );
}
