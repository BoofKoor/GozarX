/**
 * Whether a broadcast/push history is worth polling.
 *
 * Polled every few seconds while a row is in flight, so it visibly finishes — but a row can outlive
 * its job (a queue flushed under it), and one stuck row kept the history, and the site overview
 * that embeds it, polling every five seconds for as long as the page stayed open. No job runs past
 * the worker's six-hour ceiling (`_BROADCAST_TIMEOUT`), so a row older than that is stuck, not busy.
 */
const JOB_CEILING_MS = 6 * 60 * 60 * 1000;

export function stillInFlight(
  rows: { status: string; created_at: string | null }[] | undefined,
  now: number = Date.now(),
): boolean {
  return (rows ?? []).some(
    (r) =>
      (r.status === "queued" || r.status === "sending") &&
      // No timestamp to judge by: keep polling, as before.
      (r.created_at === null || now - new Date(r.created_at).getTime() < JOB_CEILING_MS),
  );
}
