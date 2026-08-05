import { clsx } from "clsx";
import { History as HistoryIcon } from "lucide-react";

import { Badge, type BadgeTone } from "@/components/ui/Badge";
import { Card } from "@/components/ui/Card";
import { EmptyState } from "@/components/ui/EmptyState";
import { useBroadcastHistory } from "@/hooks/useBroadcast";
import { useI18n, type MessageKey } from "@/i18n";
import { faRelative, formatNumber } from "@/lib/format";

const STATUS: Record<string, { key: MessageKey; tone: BadgeTone }> = {
  queued: { key: "bc.hist.queued", tone: "neutral" },
  scheduled: { key: "bc.hist.scheduled", tone: "neutral" },
  sending: { key: "bc.hist.sending", tone: "brand" },
  done: { key: "bc.hist.done", tone: "success" },
  failed: { key: "bc.hist.failed", tone: "danger" },
};

/**
 * Past broadcasts, and how each one went.
 *
 * The outcome is THREE figures, not one bar. "Removed" carries its own colour because the rule
 * behind it is the one an operator has to trust: a user is dropped only on a genuine
 * blocked/deactivated error and never on a transient one. Folded into "failed" that distinction
 * disappears, and a broadcast that pruned 70 dead accounts looks identical to one that hit 70
 * network errors.
 */
export function BroadcastHistory() {
  const { t } = useI18n();
  const { data } = useBroadcastHistory();
  const rows = data ?? [];

  return (
    <Card className="space-y-3">
      <div className="flex items-center gap-3">
        <h3 className="flex-1 text-sm font-bold text-content">{t("bc.history")}</h3>
        <span className="flex flex-wrap gap-x-3 gap-y-1 text-[11px] text-content-subtle">
          <Key tone="bg-success-500" label={t("bc.hist.sent")} />
          <Key tone="bg-danger-500" label={t("bc.hist.failedN")} />
          <Key tone="bg-warning-500" label={t("bc.hist.removed")} />
        </span>
      </div>

      {rows.length === 0 ? (
        <EmptyState icon={HistoryIcon} title={t("bc.hist.empty")} className="py-8" />
      ) : (
        <ul className="divide-y divide-line">
          {rows.map((r) => {
            const total = Math.max(1, r.recipients);
            const meta = STATUS[r.status];
            return (
              <li key={r.id} className="flex items-center gap-3 py-2.5">
                <Badge tone={meta?.tone ?? "neutral"}>{meta ? t(meta.key) : r.status}</Badge>
                <span className="min-w-0 flex-1">
                  <b className="block truncate text-[13px] font-semibold text-content">{r.body}</b>
                  <span className="mt-1.5 flex h-1.5 overflow-hidden rounded-full bg-line">
                    <i className="bg-success-500" style={{ width: pct(r.sent, total) }} />
                    <i className="bg-danger-500" style={{ width: pct(r.failed, total) }} />
                    <i className="bg-warning-500" style={{ width: pct(r.removed, total) }} />
                  </span>
                </span>
                <span className="shrink-0 text-end">
                  {/* The pair needs its OWN `dir`: an isolate is not enough, and «۸٬۲۹۸ / ۸٬۴۱۲»
                      renders reversed under an RTL base — the row then claims it sent more than
                      the whole audience. */}
                  <span dir="ltr" className="block text-xs tabular-nums text-content-muted">
                    {formatNumber(r.sent)} / {formatNumber(r.recipients)}
                  </span>
                  <time className="block text-[11px] text-content-subtle">
                    {faRelative(r.scheduled_for ?? r.created_at)}
                  </time>
                </span>
              </li>
            );
          })}
        </ul>
      )}
    </Card>
  );
}

function pct(n: number, total: number): string {
  return `${Math.min(100, (n / total) * 100)}%`;
}

function Key({ tone, label }: { tone: string; label: string }) {
  return (
    <span className="inline-flex items-center gap-1.5">
      <i className={clsx("h-2 w-2 rounded-sm", tone)} aria-hidden />
      {label}
    </span>
  );
}
