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

/** "YYYY-MM-DD" → "MM/DD" for compact chart axis labels. */
export function shortDay(iso: string): string {
  const parts = iso.split("-");
  return parts.length === 3 ? `${parts[1]}/${parts[2]}` : iso;
}

/** Split a comma-separated locations field (ASCII or Persian comma) into a trimmed, non-empty list. */
export function splitLocations(raw: string): string[] {
  return raw
    .split(/[,،]/)
    .map((s) => s.trim())
    .filter(Boolean);
}
