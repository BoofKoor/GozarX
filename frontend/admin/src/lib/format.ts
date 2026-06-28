// Small display helpers.

/** Group digits for readability (locale-agnostic so tests are stable). */
export function formatNumber(n: number): string {
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
