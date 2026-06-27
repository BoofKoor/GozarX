import { Area, AreaChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";

import { Card } from "@/components/ui/Card";
import { shortDay } from "@/lib/format";
import type { DayPoint } from "@/types/api";

export function ClaimsChart({ data }: { data: DayPoint[] }) {
  const points = data.map((d) => ({ day: shortDay(d.day), count: d.count }));
  return (
    <Card>
      <div className="mb-4 text-sm font-medium text-slate-600 dark:text-slate-300">
        دریافت کانفیگ (۱۴ روز اخیر)
      </div>
      {/* Charts read left-to-right even in an RTL UI (dates ascending). */}
      <div className="h-64" dir="ltr">
        <ResponsiveContainer width="100%" height="100%">
          <AreaChart data={points} margin={{ top: 8, right: 8, left: -16, bottom: 0 }}>
            <defs>
              <linearGradient id="claims" x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stopColor="#7CB000" stopOpacity={0.4} />
                <stop offset="100%" stopColor="#7CB000" stopOpacity={0} />
              </linearGradient>
            </defs>
            <XAxis dataKey="day" tick={{ fontSize: 11 }} />
            <YAxis allowDecimals={false} width={32} tick={{ fontSize: 11 }} />
            <Tooltip />
            <Area
              type="monotone"
              dataKey="count"
              stroke="#7CB000"
              strokeWidth={2}
              fill="url(#claims)"
            />
          </AreaChart>
        </ResponsiveContainer>
      </div>
    </Card>
  );
}
