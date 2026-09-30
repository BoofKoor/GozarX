// Countdown deadlines on the CLIENT's clock, from the server's absolute instants.
//
// The server sends an instant (`cooldown_until`, `expires_at`) plus `server_time`, its own clock when
// it answered. Counting to the instant with the phone's clock alone breaks on a phone whose clock is
// wrong — common enough that the FAQ tells people to check it — so the offset between the two clocks
// at receipt is taken out. An older backend sends only the rounded human string ("7h 12m"), which is
// parsed as a fallback: up to 59s off, and "0m" under a minute, which is why the instants exist.

/** "7h 12m" / "۷ ساعت ۱۲ دقیقه" → seconds (0 when nothing parses). */
export function parseDuration(s: string): number {
  const norm = s.replace(/[۰-۹]/g, (d) => "۰۱۲۳۴۵۶۷۸۹".indexOf(d).toString());
  const h = /(\d+)\s*(h|ساعت)/.exec(norm);
  const m = /(\d+)\s*(m|دقیقه|min)/.exec(norm);
  const sec = /(\d+)\s*(s|ثانیه|sec)/.exec(norm);
  return (h ? +h[1] * 3600 : 0) + (m ? +m[1] * 60 : 0) + (sec ? +sec[1] : 0);
}

/**
 * The client-clock millisecond at which `instant` arrives, or null when unknown.
 * `receivedAt` is Date.now() when the response carrying `serverTime` arrived.
 */
export function clientDeadline(
  instant: string | null | undefined,
  serverTime: string | null | undefined,
  receivedAt: number,
  fallback?: string | null,
): number | null {
  const at = instant ? Date.parse(instant) : NaN;
  if (!Number.isNaN(at)) {
    const server = serverTime ? Date.parse(serverTime) : NaN;
    const offset = Number.isNaN(server) ? 0 : server - receivedAt;
    return at - offset;
  }
  if (fallback && fallback !== "—") return receivedAt + parseDuration(fallback) * 1000;
  return null;
}
