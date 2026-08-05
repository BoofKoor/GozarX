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
import { useSeriesAnimation } from "@/hooks/useReducedMotion";
import { CHART_MARGIN, Y_AXIS_WIDTH, chartTheme, seriesColor } from "@/lib/chartTheme";
import { shortDay } from "@/lib/format";
import type { DayPoint } from "@/types/api";
import { useI18n } from "@/i18n";

/** Running total of users across the window — derived from signups so the curve ends at `total`
 *  (baseline = total minus the signups inside the window). No extra backend field needed. */
export function CumulativeUsersChart({ signups, total }: { signups: DayPoint[]; total: number }) {
  const { t } = useI18n();
  const inWindow = signups.reduce((s, p) => s + p.count, 0);
  let acc = total - inWindow;
  const points = signups.map((p) => {
    acc += p.count;
    return { label: shortDay(p.day), total: acc };
  });
  const theme = chartTheme(useIsDark());
  const anim = useSeriesAnimation();
  const color = seriesColor(0);

  return (
    <Card>
      <CardHeader title={t("d.cumulative")} />
      <ChartFrame height="h-56" empty={points.length === 0}>
        <ResponsiveContainer width="100%" height="100%">
          <AreaChart data={points} margin={CHART_MARGIN}>
            <defs>
              <AreaGradient id="g-cumulative" color={color} />
            </defs>
            <CartesianGrid {...gridProps(theme)} />
            <XAxis dataKey="label" {...axisProps(theme)} />
            <YAxis allowDecimals={false} width={Y_AXIS_WIDTH} {...axisProps(theme)} />
            <Tooltip {...theme.tooltip} />
            <Area
              {...anim}
              type="monotone"
              dataKey="total"
              name={t("d.cumulative.total")}
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
