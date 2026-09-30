/**
 * The operator's clock.
 *
 * Every hour the panel reports — the broadcast strip, the peak hour, the heatmap — is an
 * Asia/Tehran hour, because that is where the server buckets activity (`gozar/config/reporting`).
 * An instant built from those hours has to be built in the same zone: `new Date().setHours(21)`
 * means 21:00 wherever the BROWSER is, so an admin on a UTC laptop scheduled "21:00" and the
 * message went out at 00:30 Tehran — while the dialog and the toast both still said 21:00.
 */
export const DISPLAY_TZ = "Asia/Tehran";

/** Minutes the zone is ahead of UTC at `at`, read from `Intl` rather than hardcoded (+03:30 today,
 *  and this stays right if the zone ever changes its rules again). */
export function zoneOffsetMinutes(at: Date, timeZone = DISPLAY_TZ): number {
  const parts = new Intl.DateTimeFormat("en-US", {
    timeZone,
    hourCycle: "h23",
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
  }).formatToParts(at);
  const get = (type: string) => Number(parts.find((p) => p.type === type)?.value ?? 0);
  const wall = Date.UTC(
    get("year"),
    get("month") - 1,
    get("day"),
    get("hour"),
    get("minute"),
    get("second"),
  );
  return Math.round((wall - Math.floor(at.getTime() / 1000) * 1000) / 60_000);
}

/** The next moment the Tehran clock reads `hour`:00 — today if that is still ahead, else tomorrow. */
export function nextZonedHour(hour: number, now: Date = new Date(), timeZone = DISPLAY_TZ): Date {
  const offset = zoneOffsetMinutes(now, timeZone) * 60_000;
  // The zone's wall clock expressed in UTC fields, so its calendar date can be read directly.
  const wall = new Date(now.getTime() + offset);
  let target =
    Date.UTC(wall.getUTCFullYear(), wall.getUTCMonth(), wall.getUTCDate(), hour) - offset;
  if (target <= now.getTime()) target += 24 * 60 * 60_000;
  return new Date(target);
}
