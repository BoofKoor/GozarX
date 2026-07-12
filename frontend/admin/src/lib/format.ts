// Small display helpers.

/** Group digits for readability (locale-agnostic so tests are stable). */
export function formatNumber(n: number): string {
  if (!Number.isFinite(n)) return "0";
  return n.toLocaleString("en-US");
}

/** Megabytes → a human size string (the settings store MB; we show GB when large). */
export function formatMb(mb: number): string {
  if (mb >= 1024) {
    const gb = mb / 1024;
    return `${Number.isInteger(gb) ? gb : gb.toFixed(1)} GB`;
  }
  return `${mb} MB`;
}

/** Bytes → a human size string (the panel reports lifetime traffic served in bytes). */
export function humanBytes(n: number): string {
  if (!Number.isFinite(n)) return "0 B";
  let v = Math.max(n, 0);
  for (const unit of ["B", "KB", "MB", "GB", "TB"]) {
    if (v < 1024) return `${unit === "B" ? Math.round(v) : v.toFixed(1)} ${unit}`;
    v /= 1024;
  }
  return `${v.toFixed(1)} PB`;
}

/** "YYYY-MM-DD" → "MM/DD" for compact chart axis labels. */
export function shortDay(iso: string): string {
  const parts = iso.split("-");
  return parts.length === 3 ? `${parts[1]}/${parts[2]}` : iso;
}

/** Seconds → a compact uptime string ("3d 4h", "12m"). */
export function humanUptime(seconds: number): string {
  const s = Math.max(0, Math.floor(seconds));
  const d = Math.floor(s / 86400);
  const h = Math.floor((s % 86400) / 3600);
  const m = Math.floor((s % 3600) / 60);
  if (d) return `${d}d ${h}h`;
  if (h) return `${h}h ${m}m`;
  return `${m}m`;
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
