import {
  Area,
  AreaChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import { AreaGradient, ChartFrame, axisProps, gridProps } from "@/components/charts/primitives";
import { Card, CardHeader } from "@/components/ui/Card";
import { useIsDark } from "@/hooks/useIsDark";
import { chartTheme, seriesColor } from "@/lib/chartTheme";
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
  const t = chartTheme(useIsDark());
  const color = seriesColor(0);

  return (
    <Card>
      <CardHeader title="رشد کاربران (تجمعی)" />
      <ChartFrame height="h-56" empty={points.length === 0}>
        <ResponsiveContainer width="100%" height="100%">
          <AreaChart data={points} margin={{ top: 8, right: 8, left: -16, bottom: 0 }}>
            <defs>
              <AreaGradient id="g-cumulative" color={color} />
            </defs>
            <CartesianGrid {...gridProps(t)} />
            <XAxis dataKey="label" {...axisProps(t)} />
            <YAxis allowDecimals={false} width={36} {...axisProps(t)} />
            <Tooltip {...t.tooltip} />
            <Area
              type="monotone"
              dataKey="total"
              name="کل کاربران"
              stroke={color}
              strokeWidth={2}
              fill="url(#g-cumulative)"
            />
          </AreaChart>
        </ResponsiveContainer>
      </ChartFrame>
    </Card>
  );
}
