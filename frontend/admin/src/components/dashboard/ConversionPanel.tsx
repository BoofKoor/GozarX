import { Card, CardHeader } from "@/components/ui/Card";
import { formatNumber } from "@/lib/format";
import type { DashboardStats } from "@/types/api";

export function ConversionPanel({ data }: { data: DashboardStats }) {
  const reminderPct = data.total_users
    ? Math.round((data.reminder_enabled / data.total_users) * 100)
    : 0;
  const bars = [
    {
      label: "نرخ تبدیل",
      pct: data.conversion_pct,
      hint: "کاربرانی که حداقل یک کانفیگ گرفته‌اند",
      color: "bg-brand",
    },
    {
      label: "یادآور روشن",
      pct: reminderPct,
      hint: `${formatNumber(data.reminder_enabled)} کاربر`,
      color: "bg-info",
    },
  ];

  return (
    <Card>
      <CardHeader title="تبدیل و دعوت" />
      <div className="space-y-4">
        {bars.map((b) => (
          <div key={b.label}>
            <div className="mb-1 flex items-center justify-between text-sm">
              <span className="text-content-muted">{b.label}</span>
              <span className="font-bold tabular-nums">{b.pct}%</span>
            </div>
            <div className="h-2 overflow-hidden rounded-full bg-surface-sunken">
              <div
                className={`h-full rounded-full ${b.color} transition-all`}
                style={{ width: `${Math.min(100, b.pct)}%` }}
              />
            </div>
            <div className="mt-1 text-xs text-content-subtle">{b.hint}</div>
          </div>
        ))}
        <div className="flex items-center justify-between border-t border-line pt-3">
          <span className="text-sm text-content-muted">میانگین دعوت به ازای کاربر</span>
          <span className="text-lg font-bold tabular-nums">{data.avg_referrals}</span>
        </div>
      </div>
    </Card>
  );
}
