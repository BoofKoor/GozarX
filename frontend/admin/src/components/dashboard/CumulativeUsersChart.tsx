import { Area, AreaChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";

import { Card, CardHeader } from "@/components/ui/Card";
import { shortDay } from "@/lib/format";
import type { DayPoint } from "@/types/api";

/** Running total of users across the window — derived from signups so the curve ends at `total`
 *  (baseline = total minus the signups inside the window). No extra backend field needed. */
export function CumulativeUsersChart({ signups, total }: { signups: DayPoint[]; total: number }) {
  const inWindow = signups.reduce((s, p) => s + p.count, 0);
  let acc = total - inWindow;
  const points = signups.map((p) => {
    acc += p.count;
    return { label: shortDay(p.day), total: acc };
  });

  return (
    <Card>
      <CardHeader title="رشد کاربران (تجمعی)" />
      <div className="h-56" dir="ltr">
        {points.length === 0 ? (
          <div className="flex h-full items-center justify-center text-sm text-slate-400">
            داده‌ای برای این بازه نیست
          </div>
        ) : (
          <ResponsiveContainer width="100%" height="100%">
            <AreaChart data={points} margin={{ top: 8, right: 8, left: -16, bottom: 0 }}>
              <defs>
                <linearGradient id="g-cumulative" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor="#7CB000" stopOpacity={0.35} />
                  <stop offset="100%" stopColor="#7CB000" stopOpacity={0} />
                </linearGradient>
              </defs>
              <XAxis dataKey="label" tick={{ fontSize: 11 }} tickLine={false} axisLine={false} />
              <YAxis
                allowDecimals={false}
                width={36}
                tick={{ fontSize: 11 }}
                tickLine={false}
                axisLine={false}
              />
              <Tooltip
                contentStyle={{ borderRadius: 12, border: "1px solid #e2e8f0", fontSize: 12 }}
              />
              <Area
                type="monotone"
                dataKey="total"
                name="کل کاربران"
                stroke="#7CB000"
                strokeWidth={2}
                fill="url(#g-cumulative)"
              />
            </AreaChart>
          </ResponsiveContainer>
        )}
      </div>
    </Card>
  );
}
