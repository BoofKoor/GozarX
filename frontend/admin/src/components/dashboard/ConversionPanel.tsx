import { Card, CardHeader } from "@/components/ui/Card";
import { formatNumber } from "@/lib/format";
import type { DashboardStats } from "@/types/api";
import { useI18n } from "@/i18n";

export function ConversionPanel({ data }: { data: DashboardStats }) {
  const { t } = useI18n();
  const reminderPct = data.total_users
    ? Math.round((data.reminder_enabled / data.total_users) * 100)
    : 0;
  const bars = [
    {
      label: t("d.conv.rate"),
      pct: data.conversion_pct,
      hint: t("d.conv.rateHint"),
      color: "bg-brand",
    },
    {
      label: t("d.conv.reminder"),
      pct: reminderPct,
      hint: t("d.conv.reminderHint", { n: formatNumber(data.reminder_enabled) }),
      color: "bg-info",
    },
  ];

  return (
    <Card>
      <CardHeader title={t("d.conv")} />
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
          <span className="text-sm text-content-muted">{t("d.conv.avgReferrals")}</span>
          <span className="text-lg font-bold tabular-nums">{data.avg_referrals}</span>
        </div>
      </div>
    </Card>
  );
}
