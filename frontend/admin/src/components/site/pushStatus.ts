import type { BadgeTone } from "@/components/ui/Badge";
import type { MessageKey } from "@/i18n";

/**
 * A push broadcast's status → its label and badge tone. Shared by the Push page's history and the
 * website overview's "last push" row: the overview printed the raw code — «queued», «sending» —
 * in a Persian sentence, because it had its own branch for `done` and nothing for the rest.
 */
export const PUSH_STATUS: Record<string, { label: MessageKey; tone: BadgeTone }> = {
  queued: { label: "sp.status.queued", tone: "neutral" },
  sending: { label: "sp.status.sending", tone: "info" },
  done: { label: "sp.status.done", tone: "success" },
  failed: { label: "sp.status.failed", tone: "danger" },
};
