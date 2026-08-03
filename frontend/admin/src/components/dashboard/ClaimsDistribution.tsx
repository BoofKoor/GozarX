import { BarChart3 } from "lucide-react";

import { Card, CardHeader } from "@/components/ui/Card";
import { formatNumber } from "@/lib/format";

const BUCKETS: { key: string; label: string }[] = [
  { key: "1", label: "۱ بار" },
  { key: "2-3", label: "۲–۳ بار" },
  { key: "4-6", label: "۴–۶ بار" },
  { key: "7+", label: "۷+ بار" },
];

/** How claims spread across users — separates one-timers from power users. A heavy left side means
 *  most people take one config and leave; a fat right tail means a loyal core. */
export function ClaimsDistribution({ data }: { data: Record<string, number> }) {
  const rows = BUCKETS.map((b) => ({ ...b, value: data[b.key] ?? 0 }));
  const max = Math.max(1, ...rows.map((r) => r.value));
  const total = rows.reduce((s, r) => s + r.value, 0);
  return (
    <Card>
      <CardHeader title="توزیع دریافت به‌ازای کاربر" icon={BarChart3} />
      {total === 0 ? (
        <div className="flex h-32 items-center justify-center text-sm text-content-subtle">
          داده‌ای نیست
        </div>
      ) : (
        <ul className="space-y-2.5">
          {rows.map((r) => (
            <li key={r.key}>
              <div className="mb-1 flex items-center justify-between text-sm">
                <span className="text-content-muted">{r.label}</span>
                <span className="tabular-nums text-content-muted">{formatNumber(r.value)}</span>
              </div>
              <div className="h-2 overflow-hidden rounded-full bg-surface-sunken">
                <div
                  className="h-full rounded-full bg-brand transition-all"
                  style={{ width: `${(r.value / max) * 100}%` }}
                />
              </div>
            </li>
          ))}
        </ul>
      )}
    </Card>
  );
}
