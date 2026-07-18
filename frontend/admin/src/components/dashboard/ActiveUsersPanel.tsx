import { Activity } from "lucide-react";

import { Badge } from "@/components/ui/Badge";
import { Card, CardHeader } from "@/components/ui/Card";
import { faPct, formatNumber } from "@/lib/format";
import type { DashboardAnalytics } from "@/types/api";

/** Active-user tiles (DAU/WAU/MAU) + stickiness = DAU/MAU. A real engagement signal beyond raw
 *  claim counts: the share of the monthly base that comes back on a given day. */
export function ActiveUsersPanel({ data }: { data: DashboardAnalytics }) {
  const tiles = [
    { label: "روزانه", sub: "DAU", value: data.dau },
    { label: "هفتگی", sub: "WAU", value: data.wau },
    { label: "ماهانه", sub: "MAU", value: data.mau },
  ];
  return (
    <Card>
      <CardHeader
        title="کاربران فعال"
        icon={Activity}
        action={<Badge tone="brand">چسبندگی {faPct(data.stickiness_pct)}</Badge>}
      />
      <div className="grid grid-cols-3 gap-3">
        {tiles.map((t) => (
          <div key={t.sub} className="rounded-xl bg-slate-50 p-3 text-center dark:bg-slate-800/50">
            <div className="text-xl font-bold tabular-nums">{formatNumber(t.value)}</div>
            <div className="mt-0.5 text-xs text-slate-500 dark:text-slate-400">{t.label}</div>
            <div className="text-[10px] uppercase tracking-wide text-slate-400" dir="ltr">
              {t.sub}
            </div>
          </div>
        ))}
      </div>
      <p className="mt-3 text-xs text-slate-400">
        کاربر فعال = دستِ‌کم یک دریافت کانفیگ در بازهٔ زمانی؛ چسبندگی سهم کاربرانی است که هر روز
        برمی‌گردند.
      </p>
    </Card>
  );
}
