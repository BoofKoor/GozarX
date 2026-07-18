// Small display helpers. The panel is fully Persian/RTL, so figures use Persian numerals and dates
// use the Jalali calendar — via the browser's built-in Intl (no extra dependency).

const _FA_DIGITS = "۰۱۲۳۴۵۶۷۸۹";

/** Map ASCII digits in a string to Persian ones (keeps units/letters/punctuation as-is). */
export function toFaDigits(s: string): string {
  return s.replace(/[0-9]/g, (d) => _FA_DIGITS[+d]);
}

const _FA_NUM = new Intl.NumberFormat("fa-IR");

/** Group digits with Persian numerals + separator (e.g. 12345 → "۱۲٬۳۴۵"). */
export function formatNumber(n: number): string {
  if (!Number.isFinite(n)) return "۰";
  return _FA_NUM.format(n);
}

/** A percentage with a Persian numeral and the Persian percent sign (e.g. 12.5 → "۱۲٫۵٪"). */
export function faPct(n: number): string {
  return `${Number.isFinite(n) ? new Intl.NumberFormat("fa-IR", { maximumFractionDigits: 1 }).format(n) : "۰"}٪`;
}

/** Megabytes → a human size string (the settings store MB; we show GB when large). */
export function formatMb(mb: number): string {
  if (mb >= 1024) {
    const gb = mb / 1024;
    return toFaDigits(`${Number.isInteger(gb) ? gb : gb.toFixed(1)} GB`);
  }
  return toFaDigits(`${mb} MB`);
}

/** Bytes → a human size string (the panel reports lifetime traffic served in bytes). */
export function humanBytes(n: number): string {
  if (!Number.isFinite(n)) return toFaDigits("0 B");
  let v = Math.max(n, 0);
  for (const unit of ["B", "KB", "MB", "GB", "TB"]) {
    if (v < 1024) return toFaDigits(`${unit === "B" ? Math.round(v) : v.toFixed(1)} ${unit}`);
    v /= 1024;
  }
  return toFaDigits(`${v.toFixed(1)} PB`);
}

const _FA_SHORT_DAY = new Intl.DateTimeFormat("fa-IR", {
  month: "2-digit",
  day: "2-digit",
  timeZone: "UTC",
});

/** "YYYY-MM-DD" → compact Jalali "MM/DD" (Persian) for chart axis labels. */
export function shortDay(iso: string): string {
  const d = new Date(iso);
  return Number.isNaN(d.getTime()) ? iso : _FA_SHORT_DAY.format(d);
}

const _FA_DATE = new Intl.DateTimeFormat("fa-IR", {
  year: "numeric",
  month: "long",
  day: "numeric",
  timeZone: "UTC",
});

/** ISO date/datetime → a full Jalali date (e.g. "۲۶ تیر ۱۴۰۵"); "—" when missing/invalid. */
export function faDate(iso: string | null | undefined): string {
  if (!iso) return "—";
  const d = new Date(iso);
  return Number.isNaN(d.getTime()) ? "—" : _FA_DATE.format(d);
}

/** Seconds → a compact uptime string ("۳d ۴h", "۱۲m"). */
export function humanUptime(seconds: number): string {
  const s = Math.max(0, Math.floor(seconds));
  const d = Math.floor(s / 86400);
  const h = Math.floor((s % 86400) / 3600);
  const m = Math.floor((s % 3600) / 60);
  if (d) return toFaDigits(`${d}d ${h}h`);
  if (h) return toFaDigits(`${h}h ${m}m`);
  return toFaDigits(`${m}m`);
}

/** Bot language code → Persian display name (the panel is RTL/Persian). */
const LANG_LABELS: Record<string, string> = { fa: "فارسی", en: "انگلیسی", ru: "روسی" };

export function langLabel(code: string): string {
  return LANG_LABELS[code] ?? code;
}

/** Split a comma-separated locations field (ASCII or Persian comma) into a trimmed, non-empty list. */
export function splitLocations(raw: string): string[] {
  return raw
    .split(/[,،]/)
    .map((s) => s.trim())
    .filter(Boolean);
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
