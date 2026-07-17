import { clsx } from "clsx";
import {
  Area,
  AreaChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import { Card, CardHeader } from "@/components/ui/Card";
import { useIsDark } from "@/hooks/useIsDark";
import { chartTheme } from "@/lib/chartTheme";
import { shortDay } from "@/lib/format";
import type { DayPoint } from "@/types/api";

const RANGES: { days: number; label: string }[] = [
  { days: 7, label: "۷ روز" },
  { days: 14, label: "۱۴ روز" },
  { days: 30, label: "۳۰ روز" },
];

/** Union the two daily series on a shared x-axis (each only carries days that had rows). */
function mergeSeries(claims: DayPoint[], signups: DayPoint[]) {
  const by = new Map<string, { day: string; claims: number; signups: number }>();
  for (const p of claims) by.set(p.day, { day: p.day, claims: p.count, signups: 0 });
  for (const p of signups) {
    const e = by.get(p.day) ?? { day: p.day, claims: 0, signups: 0 };
    e.signups = p.count;
    by.set(p.day, e);
  }
  return [...by.values()]
    .sort((a, b) => a.day.localeCompare(b.day))
    .map((p) => ({ ...p, label: shortDay(p.day) }));
}

export function ActivityChart({
  claims,
  signups,
  days,
  onDaysChange,
}: {
  claims: DayPoint[];
  signups: DayPoint[];
  days: number;
  onDaysChange: (d: number) => void;
}) {
  const points = mergeSeries(claims, signups);
  const t = chartTheme(useIsDark());
  return (
    <Card>
      <CardHeader
        title="روند فعالیت"
        action={
          <div className="flex items-center gap-1 rounded-lg bg-slate-100 p-0.5 dark:bg-slate-800">
            {RANGES.map(({ days: d, label }) => (
              <button
                key={d}
                onClick={() => onDaysChange(d)}
                className={clsx(
                  "rounded-md px-2.5 py-1 text-xs font-medium transition",
                  days === d
                    ? "bg-white text-brand shadow-sm dark:bg-slate-900"
                    : "text-slate-500 hover:text-slate-700 dark:hover:text-slate-300",
                )}
              >
                {label}
              </button>
            ))}
          </div>
        }
      />
      <div className="mb-3 flex items-center gap-4 text-xs text-slate-500">
        <span className="flex items-center gap-1.5">
          <span className="h-2 w-2 rounded-full bg-brand" /> دریافت کانفیگ
        </span>
        <span className="flex items-center gap-1.5">
          <span className="h-2 w-2 rounded-full bg-info" /> کاربران جدید
        </span>
      </div>
      {/* Charts read left-to-right even in an RTL UI (dates ascending). */}
      <div className="h-64" dir="ltr">
        {points.length === 0 ? (
          <div className="flex h-full items-center justify-center text-sm text-slate-400">
            داده‌ای برای این بازه نیست
          </div>
        ) : (
          <ResponsiveContainer width="100%" height="100%">
            <AreaChart data={points} margin={{ top: 8, right: 8, left: -16, bottom: 0 }}>
              <defs>
                <linearGradient id="g-claims" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor="#7CB000" stopOpacity={0.35} />
                  <stop offset="100%" stopColor="#7CB000" stopOpacity={0} />
                </linearGradient>
                <linearGradient id="g-signups" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor="#0ea5e9" stopOpacity={0.3} />
                  <stop offset="100%" stopColor="#0ea5e9" stopOpacity={0} />
                </linearGradient>
              </defs>
              <CartesianGrid strokeDasharray="3 3" vertical={false} stroke={t.grid} />
              <XAxis
                dataKey="label"
                tick={{ fontSize: 11, fill: t.axis }}
                tickLine={false}
                axisLine={false}
              />
              <YAxis
                allowDecimals={false}
                width={32}
                tick={{ fontSize: 11, fill: t.axis }}
                tickLine={false}
                axisLine={false}
              />
              <Tooltip {...t.tooltip} />
              <Area
                type="monotone"
                dataKey="signups"
                name="کاربران جدید"
                stroke="#0ea5e9"
                strokeWidth={2}
                fill="url(#g-signups)"
              />
              <Area
                type="monotone"
                dataKey="claims"
                name="دریافت کانفیگ"
                stroke="#7CB000"
                strokeWidth={2}
                fill="url(#g-claims)"
              />
            </AreaChart>
          </ResponsiveContainer>
        )}
      </div>
    </Card>
  );
}
