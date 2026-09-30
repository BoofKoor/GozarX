// Locale helpers shared by the server and the browser: the two locales, direction, digits, token
// filling and relative time. The copy itself is NOT here — it lives in `lib/copy` and reaches the
// browser as the one locale the page renders (C-56); a component in the browser reads it through
// `useT()` (`lib/useT`). Importing the dictionaries from a client module would put both locales'
// every string back into the bundle, which is what this split took out.

export const LOCALES = ["fa", "en"] as const;
export type Locale = (typeof LOCALES)[number];
export const DEFAULT_LOCALE: Locale = "fa";

export function isLocale(v: string): v is Locale {
  return (LOCALES as readonly string[]).includes(v);
}
export function dir(locale: Locale): "rtl" | "ltr" {
  return locale === "fa" ? "rtl" : "ltr";
}

// Latin → Persian digits for fa (the design renders all numerals localized). Technical strings
// (config links, transfer codes) stay Latin/LTR — never run this on those. The separators between
// two digits count too: "1.5" becomes «۱٫۵» and "12,000" «۱۲٬۰۰۰», the marks Intl's fa-IR output
// already uses — a hand-built «۱.۵» beside an Intl «۹۹٫۷» spelled one idea two ways.
export function faDigits(s: string | number, locale: Locale): string {
  const str = String(s);
  if (locale !== "fa") return str;
  return str
    .replace(/(\d)\.(?=\d)/g, "$1٫")
    .replace(/(\d),(?=\d{3}(?!\d))/g, "$1٬")
    .replace(/\d/g, (d) => "۰۱۲۳۴۵۶۷۸۹"[+d]);
}

// Substitute `{token}`s in a copy string. Returns null when any token has no value, so the caller
// hides the sentence instead of printing a guess ("24") or a raw "{h}". A string with no tokens —
// e.g. a panel override that dropped them — comes back unchanged.
export function fill(
  text: string,
  tokens: Record<string, string | number | null | undefined>,
): string | null {
  let missing = false;
  const out = text.replace(/\{(\w+)\}/g, (whole, key: string) => {
    const v = tokens[key];
    if (v === null || v === undefined || v === "") {
      missing = true;
      return whole;
    }
    return String(v);
  });
  return missing ? null : out;
}

// Copyright year, localized: Jalali for fa (Intl, Persian digits), Gregorian for en. Compute this on
// the SERVER and pass the result down — reading `new Date()` during render on both server (UTC) and
// client (the viewer's zone, e.g. UTC+3:30) would disagree near a year boundary and trip a React
// hydration mismatch that re-renders the whole tree.
export function copyrightYear(locale: Locale): string {
  try {
    return locale === "fa"
      ? new Intl.DateTimeFormat("fa-IR", { year: "numeric" }).format(new Date())
      : String(new Date().getFullYear());
  } catch {
    return locale === "fa" ? "۱۴۰۵" : "2026";
  }
}

// Relative time ("2h ago" / "۲ ساعت پیش") for the claim history. Locale-native via Intl (fa already
// renders Persian digits), client-only, from an ISO timestamp. Returns "" for an unparseable input.
export function timeAgo(iso: string, locale: Locale): string {
  const then = new Date(iso).getTime();
  if (Number.isNaN(then)) return "";
  const sec = Math.round((then - Date.now()) / 1000); // negative = in the past
  const rtf = new Intl.RelativeTimeFormat(locale, { numeric: "auto" });
  const abs = Math.abs(sec);
  const [div, unit]: [number, Intl.RelativeTimeFormatUnit] =
    abs < 60 ? [1, "second"]
    : abs < 3600 ? [60, "minute"]
    : abs < 86400 ? [3600, "hour"]
    : abs < 2592000 ? [86400, "day"]
    : abs < 31536000 ? [2592000, "month"]
    : [31536000, "year"];
  return rtf.format(Math.round(sec / div), unit);
}

export type Translator = (key: string) => string;

/** Panel-authored overrides for design-copy keys (GET /api/public/site-copy → `overrides`). */
export type CopyOverrides = Record<string, string> | undefined;
