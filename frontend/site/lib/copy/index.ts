import type { CopyOverrides, Locale, Translator } from "@/lib/i18n";
import { CHROME } from "@/lib/copy/chrome";
import { DESIGN_COPY } from "@/lib/copy/design";

// The site's copy, for SERVER code. Both locales' dictionaries are imported here and nowhere a
// browser bundle can reach: they were ~70 KB (21 KB gzip) of JavaScript on every first visit, half
// of it the other language and a third of it keys nothing read (C-56). A component in the browser
// gets the ONE locale the page renders, resolved here by `clientCopy` and handed down by the root
// layout (`CopyProvider` / `useT`).
//
// Lookup order: admin overrides, then the chrome keys, then the design copy (the faithful per-page
// copy from the Phase 0-8 artifacts), then the fa design copy, then the raw key. So the rebuilt
// design components (design keys) and the older content pages (dotted keys) both resolve.
//
// `overrides` is what makes site copy editable from the admin panel. It only ever ADDS a layer on
// top: with no backend, an unedited install or a failed fetch, the lookup is the in-code copy.
export function translator(locale: Locale, overrides?: CopyOverrides): Translator {
  const chrome = CHROME[locale] ?? CHROME.fa;
  const design = DESIGN_COPY[locale] ?? DESIGN_COPY.fa;
  const designFa = DESIGN_COPY.fa;
  return (key: string) => overrides?.[key] ?? chrome[key] ?? design[key] ?? designFa[key] ?? key;
}

/** Every key, resolved for one locale with the panel's overrides applied — what the browser reads.
 *  Resolved on the server so the lookup order above has exactly one implementation. */
export function clientCopy(locale: Locale, overrides?: CopyOverrides): Record<string, string> {
  const t = translator(locale, overrides);
  const keys = new Set([
    ...Object.keys(DESIGN_COPY.fa),
    ...Object.keys(DESIGN_COPY[locale] ?? {}),
    ...Object.keys(CHROME[locale] ?? {}),
  ]);
  const out: Record<string, string> = {};
  for (const k of keys) out[k] = t(k);
  return out;
}
