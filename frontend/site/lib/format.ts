import { type Locale, faDigits } from "@/lib/i18n";

// ONE way to print a volume (C-47). The site printed it three ways — the backend's `human_bytes`
// string («۱ GB», «۳۸۰ MB»), a hand-built «+۵۰۰ MB», and «+۳۰۰ مگابایت» — and the Latin unit inside
// Persian copy is what reversed the daily-allowance chip into «GB ۱». In Persian the unit is a
// Persian WORD, so there is no Latin run left to reorder; in English it is the usual symbol.
//
// 1024-based with one decimal and a round value dropping its ".0", like the backend's `human_bytes`
// (so a figure the server computes and one computed here agree), in the locale's digits with «٫»
// as the decimal mark. Always from BYTES: the API sends `*_bytes` for exactly this.

export const MB = 1024 * 1024;

const UNITS: Record<Locale, readonly string[]> = {
  fa: ["بایت", "کیلوبایت", "مگابایت", "گیگابایت", "ترابایت"],
  en: ["B", "KB", "MB", "GB", "TB"],
};

/** The number and the unit apart, for layouts that set them separately (a tile's figure over its
 *  unit). */
export function volumeParts(bytes: number, locale: Locale): { num: string; unit: string } {
  let v = Math.max(0, bytes);
  let i = 0;
  while (v >= 1024 && i < UNITS.en.length - 1) {
    v /= 1024;
    i += 1;
  }
  const num = i === 0 ? String(Math.round(v)) : v.toFixed(1).replace(/\.0$/, "");
  return { num: faDigits(num, locale), unit: UNITS[locale][i] };
}

/** «۱٫۵ گیگابایت» / "1.5 GB". */
export function formatVolume(bytes: number, locale: Locale): string {
  const { num, unit } = volumeParts(bytes, locale);
  return `${num} ${unit}`;
}

/** A configured reward (always megabytes in settings) as a volume. */
export function formatMb(mb: number, locale: Locale): string {
  return formatVolume(mb * MB, locale);
}

// ONE way to name a few places in a sentence (C-53): «آلمان، هلند و فنلاند» / "Germany, Netherlands
// and Finland", and past `max` «آلمان، هلند، فنلاند و بیشتر» / "… and more". Hand-joined rather than
// Intl.ListFormat, whose Persian pattern is «آلمان، هلند، و فنلاند» with marks around the commas.
// Callers pass LABELS (flags.locLabel), never remarks: the sentence is read, not matched.
const LIST_WORDS: Record<Locale, { sep: string; and: string; more: string }> = {
  fa: { sep: "، ", and: " و ", more: "بیشتر" },
  en: { sep: ", ", and: " and ", more: "more" },
};

export function formatPlaces(names: string[], locale: Locale, max = 3): string | null {
  if (names.length === 0) return null;
  const w = LIST_WORDS[locale];
  const shown = names.slice(0, max);
  if (names.length > max) return `${shown.join(w.sep)}${w.and}${w.more}`;
  if (shown.length === 1) return shown[0];
  return `${shown.slice(0, -1).join(w.sep)}${w.and}${shown[shown.length - 1]}`;
}
