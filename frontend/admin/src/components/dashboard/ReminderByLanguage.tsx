import { BellRing } from "lucide-react";

import { Card, CardHeader } from "@/components/ui/Card";
import { faPct, formatNumber, langLabel } from "@/lib/format";
import type { LangReminder } from "@/types/api";

/** Reminder opt-in split by language — the engagement signal broken out by cohort instead of one
 *  global number. Each row shows the on/off ratio and the opt-in percentage. */
export function ReminderByLanguage({ data }: { data: LangReminder[] }) {
  const rows = [...data].sort((a, b) => b.on + b.off - (a.on + a.off));
  return (
    <Card>
      <CardHeader title="یادآور بر حسب زبان" icon={BellRing} />
      {rows.length === 0 ? (
        <div className="flex h-32 items-center justify-center text-sm text-content-subtle">
          داده‌ای نیست
        </div>
      ) : (
        <ul className="space-y-3">
          {rows.map((r) => {
            const total = r.on + r.off || 1;
            const onPct = (r.on / total) * 100;
            return (
              <li key={r.label}>
                <div className="mb-1 flex items-center justify-between text-sm">
                  <span className="text-content-muted">{langLabel(r.label)}</span>
                  <span className="text-xs text-content-subtle">
                    {formatNumber(r.on)} روشن · {faPct((r.on / total) * 100)}
                  </span>
                </div>
                <div className="flex h-2 overflow-hidden rounded-full bg-surface-sunken">
                  <div className="h-full bg-brand" style={{ width: `${onPct}%` }} />
                </div>
              </li>
            );
          })}
        </ul>
      )}
    </Card>
  );
}
