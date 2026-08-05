// Small display helpers. Every one of them follows the ACTIVE locale rather than hardcoding
// Persian: `getLocale()` is a module-level value the i18n provider writes, so these stay plain
// functions callable from the ~140 places that are not hooks, and still flip with the language.
//
// In Persian the panel shows Persian numerals and Jalali dates; in English, Latin numerals and
// Gregorian dates. Both come from the browser's built-in Intl — no extra dependency.

import { getLocale, localeTag } from "@/i18n";

const _FA_DIGITS = "۰۱۲۳۴۵۶۷۸۹";

/**
 * Map ASCII digits — and the decimal point between two of them — to the locale's own.
 *
 * The separator matters: `Intl` renders «۳۷٫۵٪» with the Persian decimal mark, so a hand-built
 * «۳.۱ TB» sitting next to it used two different separators for the same idea. Only a dot BETWEEN
 * digits is converted, so a sentence's full stop and a "v1.2" style label are left alone.
 */
export function localizeDigits(s: string): string {
  if (getLocale() !== "fa") return s;
  return s.replace(/[0-9]/g, (d) => _FA_DIGITS[+d]).replace(/(?<=[۰-۹])\.(?=[۰-۹])/g, "٫");
}

// Intl formatters are expensive to construct, so keep one per locale instead of one per call.
const _cache = new Map<string, Intl.NumberFormat | Intl.DateTimeFormat>();
function memo<T extends Intl.NumberFormat | Intl.DateTimeFormat>(key: string, make: () => T): T {
  const hit = _cache.get(`${localeTag()}|${key}`);
  if (hit) return hit as T;
  const made = make();
  _cache.set(`${localeTag()}|${key}`, made);
  return made;
}

/** Group digits with the locale's numerals + separator (12345 → "۱۲٬۳۴۵" / "12,345"). */
export function formatNumber(n: number): string {
  if (!Number.isFinite(n)) return localizeDigits("0");
  return memo("num", () => new Intl.NumberFormat(localeTag())).format(n);
}

/** A percentage with the locale's numerals and percent sign (12.5 → "۱۲٫۵٪" / "12.5%"). */
export function faPct(n: number | null | undefined): string {
  const value =
    n != null && Number.isFinite(n)
      ? memo("pct", () => new Intl.NumberFormat(localeTag(), { maximumFractionDigits: 1 })).format(
          n,
        )
      : localizeDigits("0");
  return `${value}${getLocale() === "fa" ? "٪" : "%"}`;
}

/**
 * Wrap a "<number> <LATIN UNIT>" quantity in a Unicode isolate.
 *
 * These strings are returned by plain functions and land inside Persian sentences, where the
 * bidi algorithm reorders them: «۱ GB» renders as «GB ۱», with the unit ahead of its own number.
 * A `dir="ltr"` span would fix it, but only at a call site — FSI…PDI travels with the string, so
 * every caller gets it for free.
 */
function isolateQuantity(s: string): string {
  return `\u2068${s}\u2069`;
}

/** Megabytes → a human size string (the settings store MB; we show GB when large). */
export function formatMb(mb: number): string {
  if (mb >= 1024) {
    const gb = mb / 1024;
    return isolateQuantity(localizeDigits(`${Number.isInteger(gb) ? gb : gb.toFixed(1)} GB`));
  }
  return isolateQuantity(localizeDigits(`${mb} MB`));
}

/** Bytes → a human size string (the panel reports lifetime traffic served in bytes). */
export function humanBytes(n: number): string {
  if (!Number.isFinite(n)) return isolateQuantity(localizeDigits("0 B"));
  let v = Math.max(n, 0);
  for (const unit of ["B", "KB", "MB", "GB", "TB"]) {
    if (v < 1024) {
      return isolateQuantity(
        localizeDigits(`${unit === "B" ? Math.round(v) : v.toFixed(1)} ${unit}`),
      );
    }
    v /= 1024;
  }
  return isolateQuantity(localizeDigits(`${v.toFixed(1)} PB`));
}

/** "YYYY-MM-DD" → a compact "MM/DD" in the locale's calendar, for chart axis labels. */
export function shortDay(iso: string): string {
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  return memo(
    "shortDay",
    () =>
      new Intl.DateTimeFormat(localeTag(), { month: "2-digit", day: "2-digit", timeZone: "UTC" }),
  ).format(d);
}

/** ISO date/datetime → a full date ("۲۶ تیر ۱۴۰۵" / "17 July 2026"); "—" when missing/invalid. */
export function faDate(iso: string | null | undefined): string {
  if (!iso) return "—";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return "—";
  return memo(
    "date",
    () =>
      new Intl.DateTimeFormat(localeTag(), {
        year: "numeric",
        month: "long",
        day: "numeric",
        timeZone: "UTC",
      }),
  ).format(d);
}

/**
 * ISO datetime → a clock time in the LOCAL zone, in the panel's language.
 *
 * Local, not UTC, unlike `faDate`/`shortDay`: those label reporting days, which are fixed Tehran
 * days, while this stamps "when was this probe taken" for whoever is looking at the screen.
 */
export function faTime(iso: string): string {
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return "—";
  return memo(
    "time",
    () => new Intl.DateTimeFormat(localeTag(), { hour: "2-digit", minute: "2-digit" }),
  ).format(d);
}

/**
 * ISO datetime → how long ago, in the panel's language ("۲ ساعت پیش" / "2 hours ago").
 *
 * `Intl.RelativeTimeFormat` rather than a hand-built table: it already knows Persian's plural rules
 * and its own numerals, so the string never has a Latin digit in it and never has to be pluralised
 * by hand. The unit is the largest one the gap fills, because "۹۰ دقیقه پیش" is a worse answer than
 * "۲ ساعت پیش" to the question the timeline is asking.
 */
const _UNITS: [Intl.RelativeTimeFormatUnit, number][] = [
  ["year", 365 * 24 * 3600],
  ["month", 30 * 24 * 3600],
  ["day", 24 * 3600],
  ["hour", 3600],
  ["minute", 60],
];

export function faRelative(iso: string | null | undefined): string {
  if (!iso) return "—";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return "—";
  const seconds = (d.getTime() - Date.now()) / 1000;
  const fmt = memoRelative();
  for (const [unit, span] of _UNITS) {
    if (Math.abs(seconds) >= span) return fmt.format(Math.round(seconds / span), unit);
  }
  return fmt.format(Math.round(seconds), "second");
}

const _relCache = new Map<string, Intl.RelativeTimeFormat>();
function memoRelative(): Intl.RelativeTimeFormat {
  const tag = localeTag();
  const hit = _relCache.get(tag);
  if (hit) return hit;
  const made = new Intl.RelativeTimeFormat(tag, { numeric: "auto" });
  _relCache.set(tag, made);
  return made;
}

/** ISO datetime → date + clock time, in the panel's language. */
export function faDateTime(iso: string): string {
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return "—";
  return memo(
    "dateTime",
    () =>
      new Intl.DateTimeFormat(localeTag(), {
        dateStyle: "short",
        timeStyle: "short",
      }),
  ).format(d);
}

/** Seconds → a compact uptime string ("۳d ۴h", "۱۲m"). */
export function humanUptime(seconds: number): string {
  const s = Math.max(0, Math.floor(seconds));
  const d = Math.floor(s / 86400);
  const h = Math.floor((s % 86400) / 3600);
  const m = Math.floor((s % 3600) / 60);
  if (d) return isolateQuantity(localizeDigits(`${d}d ${h}h`));
  if (h) return isolateQuantity(localizeDigits(`${h}h ${m}m`));
  return isolateQuantity(localizeDigits(`${m}m`));
}

/** Bot language code → its display name, in the panel's own language. */
const LANG_LABELS: Record<string, Record<string, string>> = {
  fa: { fa: "فارسی", en: "انگلیسی", ru: "روسی" },
  en: { fa: "Persian", en: "English", ru: "Russian" },
};

export function langLabel(code: string): string {
  return LANG_LABELS[getLocale()]?.[code] ?? code;
}

/** Split a comma-separated locations field (ASCII or Persian comma) into a trimmed, non-empty list. */
export function splitLocations(raw: string): string[] {
  return raw
    .split(/[,،]/)
    .map((s) => s.trim())
    .filter(Boolean);
}

/** Join a list with the locale's own comma — the inverse of `splitLocations`. */
export function joinList(list: string[]): string {
  return list.join(getLocale() === "fa" ? "، " : ", ");
}

// The formatting tags Telegram actually renders (attribute-less; <a href> handled separately).
const TG_TAGS = "b|strong|i|em|u|ins|s|strike|del|code|pre|blockquote|tg-spoiler";

/**
 * Render a Telegram-formatted message body as SAFE preview HTML.
 *
 * Everything is HTML-escaped first, then only Telegram's small supported tag subset is re-enabled —
 * so pasted markup like `<img onerror=…>` or `<script>` can never execute in the admin origin
 * (where the JWTs live in localStorage). Links are re-enabled only when the href is an
 * http(s)/tg scheme. This replaces a raw `dangerouslySetInnerHTML` of the textarea content.
 */
export function telegramPreviewHtml(raw: string): string {
  const escaped = raw.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
  return escaped
    .replace(new RegExp(`&lt;(/?(?:${TG_TAGS}))&gt;`, "gi"), "<$1>")
    .replace(/&lt;a\s+href=(&quot;|"|')([^"'&<>]+)\1&gt;/gi, (m, _q, href) =>
      /^(https?:\/\/|tg:\/\/)/i.test(href)
        ? `<a href="${href}" target="_blank" rel="noopener noreferrer">`
        : m,
    )
    .replace(/&lt;\/a&gt;/gi, "</a>");
}
