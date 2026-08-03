import { Cell, Pie, PieChart, ResponsiveContainer } from "recharts";

import { Card, CardHeader } from "@/components/ui/Card";
import { useIsDark } from "@/hooks/useIsDark";
import { tokenColor } from "@/lib/chartTheme";
import { formatNumber, humanBytes } from "@/lib/format";
import type { DashboardStats } from "@/types/api";

// Remnawave user statuses → Persian label + the semantic token that carries their meaning.
const STATUS_META: Record<string, { label: string; token: string }> = {
  ACTIVE: { label: "فعال", token: "success-500" },
  LIMITED: { label: "محدود", token: "warning-500" },
  EXPIRED: { label: "منقضی", token: "danger-500" },
  DISABLED: { label: "غیرفعال", token: "text-subtle" },
};

export function TrialHealthPanel({ data }: { data: DashboardStats }) {
  useIsDark(); // slice colours come from CSS tokens — re-render when the theme flips
  const slices = Object.entries(data.panel_status_counts)
    .filter(([, n]) => n > 0)
    .map(([status, n]) => ({
      name: STATUS_META[status]?.label ?? status,
      value: n,
      color: tokenColor(STATUS_META[status]?.token ?? "line-strong"),
    }));
  const total = slices.reduce((s, x) => s + x.value, 0);

  return (
    <Card>
      <CardHeader title="سلامت سرویس (پنل)" />
      <div className="flex items-center gap-4">
        <div className="h-36 w-36 shrink-0" dir="ltr">
          {total === 0 ? (
            <div className="flex h-full items-center justify-center text-xs text-content-subtle">
              بدون داده
            </div>
          ) : (
            <ResponsiveContainer width="100%" height="100%">
              <PieChart>
                <Pie
                  data={slices}
                  dataKey="value"
                  nameKey="name"
                  innerRadius={38}
                  outerRadius={62}
                  paddingAngle={2}
                  stroke="none"
                >
                  {slices.map((s) => (
                    <Cell key={s.name} fill={s.color} />
                  ))}
                </Pie>
              </PieChart>
            </ResponsiveContainer>
          )}
        </div>
        <ul className="flex-1 space-y-1.5">
          {slices.map((s) => (
            <li key={s.name} className="flex items-center gap-2 text-sm">
              <span className="h-2.5 w-2.5 rounded-full" style={{ backgroundColor: s.color }} />
              <span className="flex-1 text-content-muted">{s.name}</span>
              <span className="font-medium tabular-nums">{formatNumber(s.value)}</span>
            </li>
          ))}
        </ul>
      </div>
      <div className="mt-4 grid grid-cols-3 gap-3 border-t border-line pt-3 text-center">
        <Metric label="ترافیک مصرفی" value={humanBytes(data.total_traffic_bytes)} />
        <Metric label="نودهای آنلاین" value={formatNumber(data.nodes_online)} />
        <Metric label="کاربران پنل" value={formatNumber(data.panel_total_users)} />
      </div>
    </Card>
  );
}

function Metric({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <div className="text-sm font-bold tabular-nums">{value}</div>
      <div className="text-xs text-content-subtle">{label}</div>
    </div>
  );
}
