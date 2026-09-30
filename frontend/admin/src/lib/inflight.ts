/**
 * Whether a broadcast/push history is worth polling.
 *
 * Polled every few seconds while a row is in flight, so it visibly finishes — but a row can outlive
 * its job (a queue flushed under it), and one stuck row kept the history, and the site overview
 * that embeds it, polling every five seconds for as long as the page stayed open. No job runs past
 * the worker's six-hour ceiling (`_BROADCAST_TIMEOUT`), so a row older than that is stuck, not busy.
 *
 * "Older" is counted from when the job could START: `scheduled_for` for a scheduled broadcast. From
 * `created_at`, one scheduled more than six hours ahead — 13:00 for the 21:00 peak — was already
 * "stuck" the moment it began sending, and its row sat on «در حال ارسال» with stale counts.
 */
const JOB_CEILING_MS = 6 * 60 * 60 * 1000;

export function stillInFlight(
  rows: { status: string; created_at: string | null; scheduled_for?: string | null }[] | undefined,
  now: number = Date.now(),
): boolean {
  return (rows ?? []).some((r) => {
    if (r.status !== "queued" && r.status !== "sending") return false;
    const started = r.scheduled_for ?? r.created_at;
    // No timestamp to judge by: keep polling, as before.
    return started === null || now - new Date(started).getTime() < JOB_CEILING_MS;
  });
}
