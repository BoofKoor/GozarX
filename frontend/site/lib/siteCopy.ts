// Server-side read of the editable hero + homepage-meta copy (/api/public/site-copy). Same pattern
// as lib/landing.ts: runs in the Next server, hits BACKEND_ORIGIN directly, ISR-revalidated so an
// admin edit in the Texts panel shows within ~5 minutes without a redeploy. Every field is nullable
// and the whole thing degrades to all-null on any failure — the caller falls back to its in-code
// copy, so `next build` with no backend and a transient outage both render fine.

import type { Locale } from "@/lib/i18n";

const BACKEND = (process.env.BACKEND_ORIGIN ?? "http://127.0.0.1:8000").replace(/\/+$/, "");
const REVALIDATE = 300;

export interface SiteCopy {
  hero_title: string | null;
  hero_sub: string | null;
  meta_title: string | null;
  meta_description: string | null;
  /** design-copy key -> panel override. Only customised keys appear; everything else falls back to
   *  the in-code DESIGN_COPY, so an unedited install renders exactly as it always did. */
  overrides: Record<string, string>;
}

const EMPTY: SiteCopy = {
  hero_title: null,
  hero_sub: null,
  meta_title: null,
  meta_description: null,
  overrides: {},
};

/** A blank string is "unset", not a value: every caller falls back with `??`, which keeps "". An
 *  older backend returned a cleared row verbatim, and the page shipped an empty <title>. */
function text(value: unknown): string | null {
  return typeof value === "string" && value.trim() ? value : null;
}

export async function fetchSiteCopy(locale: Locale): Promise<SiteCopy> {
  try {
    const res = await fetch(`${BACKEND}/api/public/site-copy?locale=${locale}`, {
      next: { revalidate: REVALIDATE },
    });
    if (!res.ok) return EMPTY;
    const data = (await res.json()) as Partial<SiteCopy>;
    return {
      hero_title: text(data.hero_title),
      hero_sub: text(data.hero_sub),
      meta_title: text(data.meta_title),
      meta_description: text(data.meta_description),
      // An older backend has no `overrides` field; default it rather than letting `undefined` through.
      overrides: data.overrides ?? {},
    };
  } catch {
    return EMPTY;
  }
}
