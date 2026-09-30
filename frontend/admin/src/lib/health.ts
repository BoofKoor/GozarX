import type { SystemHealth } from "@/types/api";

/** The backend's `_PENDING_BACKLOG`: the service reads degraded only when pending EXCEEDS this. */
export const PENDING_BACKLOG = 50;

/**
 * What the Telegram webhook is doing, decided in ONE place.
 *
 * The system page's card and the dashboard's health row each had their own rule, and neither read
 * `url_set`: a bot whose webhook registration failed at startup (or was deleted elsewhere) receives
 * no update at all, yet both showed green «فعال». The dashboard row also stayed green with Telegram
 * unreachable or 50+ updates queued, and showed a red «تنظیم نشده» while the snapshot was still
 * LOADING. The server's overall status reads the same fields (`services/health._overall`).
 */
export type WebhookState =
  "checking" | "off" | "unreachable" | "unregistered" | "error" | "backlog" | "ok";

export function webhookState(health: SystemHealth | undefined): WebhookState {
  if (!health) return "checking";
  const { webhook, telegram } = health;
  if (!webhook.configured) return "off";
  if (!telegram.ok) return "unreachable"; // cannot tell whether it is registered
  if (!webhook.url_set) return "unregistered";
  if (webhook.recent_error) return "error";
  if (webhook.pending > PENDING_BACKLOG) return "backlog";
  return "ok";
}
