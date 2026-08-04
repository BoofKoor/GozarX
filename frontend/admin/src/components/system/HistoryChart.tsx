import {
  Area,
  CartesianGrid,
  ComposedChart,
  Line,
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
import { useI18n } from "@/i18n";
import { chartTheme, seriesColor } from "@/lib/chartTheme";
import { formatNumber } from "@/lib/format";
import type { HealthSample } from "@/types/api";

const RANGES = [60, 360, 1440];

function hhmm(iso: string): string {
  const d = new Date(iso);
  return Number.isNaN(d.getTime())
    ? ""
    : `${String(d.getHours()).padStart(2, "0")}:${String(d.getMinutes()).padStart(2, "0")}`;
}

export function HistoryChart({
  samples,
  minutes,
  onMinutesChange,
}: {
  samples: HealthSample[];
  minutes: number;
  onMinutesChange: (m: number) => void;
}) {
  // Keep a failed Telegram latency probe (api_ms === null) as a GAP, not 0 — a 0 ms reading on a
  // latency axis reads as "excellent" and would hide an outage at the chart floor.
  const { t: tr } = useI18n();
  const points = samples.map((s) => ({ t: hhmm(s.ts), api: s.api_ms, pending: s.pending }));
  const ranges = RANGES.map((value) => ({
    value,
    label: tr("sys.chart.hours", { n: formatNumber(value / 60) }),
  }));
  const t = chartTheme(useIsDark());
  const apiColor = seriesColor(0);
  const pendingColor = seriesColor(1);

  return (
    <Card>
      <CardHeader
        title={tr("sys.chart.title")}
        action={
          <Segmented
            value={minutes}
            onChange={onMinutesChange}
            options={ranges}
            size="sm"
            ariaLabel={tr("sys.chart.range")}
          />
        }
      />
      <ChartLegend
        items={[
          { label: tr("sys.chart.api"), color: apiColor },
          { label: tr("sys.chart.pending"), color: pendingColor },
        ]}
      />
      <ChartFrame height="h-60" empty={points.length === 0} emptyLabel={tr("sys.chart.empty")}>
        <ResponsiveContainer width="100%" height="100%">
          {/* No negative left margin: it pulled a 3-digit localized tick off the frame and the
              axis read "40" where the value was 140. */}
          <ComposedChart data={points} margin={{ top: 8, right: 4, left: 4, bottom: 0 }}>
            <defs>
              <AreaGradient id="g-api" color={apiColor} />
            </defs>
            <CartesianGrid {...gridProps(t)} />
            <XAxis dataKey="t" minTickGap={32} {...axisProps(t)} />
            <YAxis yAxisId="api" width={44} {...axisProps(t)} />
            <YAxis
              yAxisId="pending"
              orientation="right"
              width={34}
              allowDecimals={false}
              {...axisProps(t)}
            />
            <Tooltip {...t.tooltip} />
            <Area
              yAxisId="api"
              type="monotone"
              dataKey="api"
              name={tr("sys.chart.latency")}
              stroke={apiColor}
              strokeWidth={2}
              fill="url(#g-api)"
              connectNulls={false}
            />
            <Line
              yAxisId="pending"
              type="monotone"
              dataKey="pending"
              name={tr("sys.chart.pendingShort")}
              stroke={pendingColor}
              strokeWidth={2}
              dot={false}
            />
          </ComposedChart>
        </ResponsiveContainer>
      </ChartFrame>
    </Card>
  );
}
