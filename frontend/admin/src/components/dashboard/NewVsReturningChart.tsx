import { Users } from "lucide-react";
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
import { Badge } from "@/components/ui/Badge";
import { Card, CardHeader } from "@/components/ui/Card";
import { useIsDark } from "@/hooks/useIsDark";
import { useSeriesAnimation } from "@/hooks/useReducedMotion";
import { CHART_MARGIN, Y_AXIS_WIDTH, chartTheme, seriesColor } from "@/lib/chartTheme";
import { faPct, shortDay } from "@/lib/format";
import type { SplitDayPoint } from "@/types/api";
import { useI18n } from "@/i18n";

/**
 * Daily claimers split into first-timers and returners, stacked.
 *
 * The plain claim count can't tell growth from repeat usage: a flat line means something very
 * different when it's all new users every day (nobody comes back) versus all returners (nothing new
 * is arriving). The badge shows the window's returning share, which is the number to watch.
 */
export function NewVsReturningChart({ data }: { data: SplitDayPoint[] }) {
  const { t } = useI18n();
  const theme = chartTheme(useIsDark());
  const anim = useSeriesAnimation();
  const newColor = seriesColor(1);
  const returningColor = seriesColor(0);
  const points = data.map((p) => ({ ...p, label: shortDay(p.day) }));

  const totalNew = data.reduce((s, p) => s + p.new, 0);
  const totalReturning = data.reduce((s, p) => s + p.returning, 0);
  const total = totalNew + totalReturning;

  return (
    <Card>
      <CardHeader
        title={t("d.newVsReturning")}
        sub={t("d.newVsReturning.sub")}
        icon={Users}
        action={
          total > 0 ? (
            <Badge tone={totalReturning >= totalNew ? "success" : "warning"}>
              {t("d.newVsReturning.share", { pct: faPct((totalReturning / total) * 100) })}
            </Badge>
          ) : undefined
        }
      />
      <ChartLegend
        items={[
          { label: t("d.returning"), color: returningColor },
          { label: t("d.new"), color: newColor },
        ]}
      />
      <ChartFrame height="h-56" empty={total === 0}>
        <ResponsiveContainer width="100%" height="100%">
          <AreaChart data={points} margin={CHART_MARGIN}>
            <defs>
              <AreaGradient id="g-returning" color={returningColor} />
              <AreaGradient id="g-new" color={newColor} />
            </defs>
            <CartesianGrid {...gridProps(theme)} />
            <XAxis dataKey="label" {...axisProps(theme)} />
            <YAxis allowDecimals={false} width={Y_AXIS_WIDTH} {...axisProps(theme)} />
            <Tooltip {...theme.tooltip} />
            <Area
              {...anim}
              type="monotone"
              stackId="claimers"
              dataKey="returning"
              name={t("d.returning")}
              stroke={returningColor}
              strokeWidth={2}
              fill="url(#g-returning)"
            />
            <Area
              {...anim}
              type="monotone"
              stackId="claimers"
              dataKey="new"
              name={t("d.new")}
              stroke={newColor}
              strokeWidth={2}
              fill="url(#g-new)"
            />
          </AreaChart>
        </ResponsiveContainer>
      </ChartFrame>
    </Card>
  );
}
