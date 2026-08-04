import { Timer } from "lucide-react";

import { Card, CardHeader } from "@/components/ui/Card";
import { faPct, formatNumber } from "@/lib/format";
import type { DashboardAnalytics } from "@/types/api";

/** How fast new users reach their first config, and what share activate same-day — the classic
 *  activation health check.
 *
 *  Both figures are WINDOWED on the page's range: the cohort is everyone whose first claim landed
 *  in it. They used to be all-time numbers sitting under a range control that could not move them,
 *  which made the control a lie for this card. */
export function ActivationPanel({ data }: { data: DashboardAnalytics }) {
  const median = data.median_hours_to_claim.value;
  return (
    <Card>
      <CardHeader title="فعال‌سازی" icon={Timer} />
      <div className="grid grid-cols-2 gap-3">
        <div className="rounded-xl bg-surface-sunken p-4">
          <div className="text-2xl font-bold tabular-nums">
            {median == null ? "—" : formatNumber(median)}
            {median != null && (
              <span className="mr-1 text-sm font-normal text-content-subtle">ساعت</span>
            )}
          </div>
          <div className="mt-1 text-xs text-content-muted">میانهٔ زمان تا اولین کانفیگ</div>
        </div>
        <div className="rounded-xl bg-surface-sunken p-4">
          <div className="text-2xl font-bold tabular-nums text-brand">
            {faPct(data.activation_24h.value)}
          </div>
          <div className="mt-1 text-xs text-content-muted">فعال‌سازی در ۲۴ ساعت اول</div>
        </div>
      </div>
      <p className="mt-3 text-xs text-content-subtle">
        بر پایهٔ {formatNumber(data.first_claimers_in_range)} کاربری که در این بازه اولین کانفیگشان
        را گرفته‌اند. در کل عمر سرویس {formatNumber(data.claimers_all_time)} نفر کانفیگ گرفته‌اند.
      </p>
    </Card>
  );
}
