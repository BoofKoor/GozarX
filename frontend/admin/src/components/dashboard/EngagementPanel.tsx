import { Radio } from "lucide-react";

import { Badge } from "@/components/ui/Badge";
import { Card, CardHeader } from "@/components/ui/Card";
import { formatNumber } from "@/lib/format";
import type { DashboardStats } from "@/types/api";

/** Week-over-week growth chip. `null` pct = no prior-week baseline (launch): show "new" only when
 *  this week actually had signups, never a misleading "0%". */
function GrowthBadge({ pct, newThisWeek }: { pct: number | null; newThisWeek: number }) {
  if (pct === null) return newThisWeek > 0 ? <Badge tone="success">✦ جدید</Badge> : null;
  if (pct === 0) return null;
  return (
    <Badge tone={pct > 0 ? "success" : "danger"}>
      {pct > 0 ? "▲" : "▼"} {Math.abs(pct)}% هفتگی
    </Badge>
  );
}

/** Live engagement from the panel: online now / last 24h / last 7d / never online (bar list). */
export function EngagementPanel({ data }: { data: DashboardStats }) {
  const rows = [
    {
      // online_now is scoped to the service's trial squad(s); the last-day/week/never figures below
      // stay panel-wide (the panel only reports those globally), so flag the scope on this row.
      label: data.online_squad_scoped ? "هم‌اکنون آنلاین (اسکواد سرویس)" : "هم‌اکنون آنلاین",
      value: data.online_now,
      color: "#22c55e",
    },
    { label: "۲۴ ساعت اخیر", value: data.online_last_day, color: "#0ea5e9" },
    { label: "۷ روز اخیر", value: data.online_last_week, color: "#7CB000" },
    { label: "هرگز آنلاین نشده", value: data.never_online, color: "#94a3b8" },
  ];
  const max = Math.max(1, ...rows.map((r) => r.value));

  return (
    <Card>
      <CardHeader
        title="تعامل کاربران"
        icon={Radio}
        action={<GrowthBadge pct={data.growth_pct} newThisWeek={data.new_this_week} />}
      />
      {!data.panel_online && (
        <div className="mb-3 rounded-lg bg-amber-50 px-3 py-2 text-xs text-amber-700 dark:bg-amber-950/40 dark:text-amber-300">
          آمار زندهٔ پنل در دسترس نیست — اعداد آنلاین صفر نمایش داده می‌شوند.
        </div>
      )}
      <ul className="space-y-3">
        {rows.map((r) => (
          <li key={r.label}>
            <div className="mb-1 flex items-center justify-between text-sm">
              <span className="text-slate-600 dark:text-slate-300">{r.label}</span>
              <span className="font-medium tabular-nums text-slate-500">
                {formatNumber(r.value)}
              </span>
            </div>
            <div className="h-2 overflow-hidden rounded-full bg-slate-100 dark:bg-slate-800">
              <div
                className="h-full rounded-full transition-all"
                style={{ width: `${(r.value / max) * 100}%`, backgroundColor: r.color }}
              />
            </div>
          </li>
        ))}
      </ul>
    </Card>
  );
}
