import {
  Area,
  AreaChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import {
  AreaGradient,
  ChartFrame,
  ChartLegend,
  axisProps,
  gridProps,
} from "@/components/charts/primitives";
import { Card, CardHeader } from "@/components/ui/Card";
import { Segmented } from "@/components/ui/Segmented";
import { useIsDark } from "@/hooks/useIsDark";
import { chartTheme, seriesColor } from "@/lib/chartTheme";
import { shortDay } from "@/lib/format";
import type { DayPoint } from "@/types/api";

const RANGES = [
  { value: 7, label: "۷ روز" },
  { value: 14, label: "۱۴ روز" },
  { value: 30, label: "۳۰ روز" },
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
  const claimsColor = seriesColor(0);
  const signupsColor = seriesColor(1);

  return (
    <Card>
      <CardHeader
        title="روند فعالیت"
        action={
          <Segmented
            value={days}
            onChange={onDaysChange}
            options={RANGES}
            size="sm"
            ariaLabel="بازهٔ نمودار"
          />
        }
      />
      <ChartLegend
        items={[
          { label: "دریافت کانفیگ", color: claimsColor },
          { label: "کاربران جدید", color: signupsColor },
        ]}
      />
      <ChartFrame empty={points.length === 0}>
        <ResponsiveContainer width="100%" height="100%">
          <AreaChart data={points} margin={{ top: 8, right: 8, left: -16, bottom: 0 }}>
            <defs>
              <AreaGradient id="g-claims" color={claimsColor} />
              <AreaGradient id="g-signups" color={signupsColor} />
            </defs>
            <CartesianGrid {...gridProps(t)} />
            <XAxis dataKey="label" {...axisProps(t)} />
            <YAxis allowDecimals={false} width={32} {...axisProps(t)} />
            <Tooltip {...t.tooltip} />
            <Area
              type="monotone"
              dataKey="signups"
              name="کاربران جدید"
              stroke={signupsColor}
              strokeWidth={2}
              fill="url(#g-signups)"
            />
            <Area
              type="monotone"
              dataKey="claims"
              name="دریافت کانفیگ"
              stroke={claimsColor}
              strokeWidth={2}
              fill="url(#g-claims)"
            />
          </AreaChart>
        </ResponsiveContainer>
      </ChartFrame>
    </Card>
  );
}
