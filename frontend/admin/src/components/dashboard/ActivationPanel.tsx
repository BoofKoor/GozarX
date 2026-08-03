import { Timer } from "lucide-react";

import { Card, CardHeader } from "@/components/ui/Card";
import { faPct, formatNumber } from "@/lib/format";
import type { DashboardAnalytics } from "@/types/api";

/** How fast new users reach their first config, and what share activate same-day — the classic
 *  activation health check. */
export function ActivationPanel({ data }: { data: DashboardAnalytics }) {
  const median = data.median_hours_to_claim;
  return (
    <Card>
      <CardHeader title="فعال‌سازی" icon={Timer} />
      <div className="grid grid-cols-2 gap-3">
        <div className="rounded-xl bg-surface-sunken p-4 dark:bg-surface-sunken/50">
          <div className="text-2xl font-bold tabular-nums">
            {median == null ? "—" : `${formatNumber(median)}`}
            {median != null && (
              <span className="mr-1 text-sm font-normal text-content-subtle">ساعت</span>
            )}
          </div>
          <div className="mt-1 text-xs text-content-muted">میانهٔ زمان تا اولین کانفیگ</div>
        </div>
        <div className="rounded-xl bg-surface-sunken p-4 dark:bg-surface-sunken/50">
          <div className="text-2xl font-bold tabular-nums text-brand">
            {faPct(data.activation_24h_pct)}
          </div>
          <div className="mt-1 text-xs text-content-muted">فعال‌سازی در ۲۴ ساعت اول</div>
        </div>
      </div>
      <p className="mt-3 text-xs text-content-subtle">
        بر پایهٔ {formatNumber(data.claimers)} کاربری که تا کنون کانفیگ گرفته‌اند.
      </p>
    </Card>
  );
}
