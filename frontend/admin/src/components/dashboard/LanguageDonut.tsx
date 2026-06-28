import { Cell, Pie, PieChart, ResponsiveContainer } from "recharts";

import { Card, CardHeader } from "@/components/ui/Card";
import { formatNumber, langLabel } from "@/lib/format";
import type { NamedCount } from "@/types/api";

const COLORS = ["#7CB000", "#0ea5e9", "#f59e0b", "#a855f7", "#ef4444"];

export function LanguageDonut({ data }: { data: NamedCount[] }) {
  const total = data.reduce((s, d) => s + d.count, 0);
  const slices = data.map((d, i) => ({
    name: langLabel(d.label),
    value: d.count,
    color: COLORS[i % COLORS.length],
  }));

  return (
    <Card>
      <CardHeader title="زبان کاربران" />
      {total === 0 ? (
        <div className="flex h-40 items-center justify-center text-sm text-slate-400">
          هنوز کاربری نیست
        </div>
      ) : (
        <div className="flex items-center gap-4">
          <div className="h-40 w-40 shrink-0" dir="ltr">
            <ResponsiveContainer width="100%" height="100%">
              <PieChart>
                <Pie
                  data={slices}
                  dataKey="value"
                  nameKey="name"
                  innerRadius={42}
                  outerRadius={68}
                  paddingAngle={2}
                  stroke="none"
                >
                  {slices.map((s) => (
                    <Cell key={s.name} fill={s.color} />
                  ))}
                </Pie>
              </PieChart>
            </ResponsiveContainer>
          </div>
          <ul className="flex-1 space-y-2">
            {slices.map((s) => (
              <li key={s.name} className="flex items-center gap-2 text-sm">
                <span className="h-2.5 w-2.5 rounded-full" style={{ backgroundColor: s.color }} />
                <span className="flex-1 text-slate-600 dark:text-slate-300">{s.name}</span>
                <span className="font-medium tabular-nums">{formatNumber(s.value)}</span>
                <span className="w-10 text-left text-xs text-slate-400 tabular-nums">
                  {Math.round((s.value / total) * 100)}%
                </span>
              </li>
            ))}
          </ul>
        </div>
      )}
    </Card>
  );
}
