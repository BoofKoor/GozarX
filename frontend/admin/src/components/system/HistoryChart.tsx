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
import { chartTheme, seriesColor } from "@/lib/chartTheme";
import type { HealthSample } from "@/types/api";

const RANGES = [
  { value: 60, label: "۱ ساعت" },
  { value: 360, label: "۶ ساعت" },
  { value: 1440, label: "۲۴ ساعت" },
];

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
  const points = samples.map((s) => ({ t: hhmm(s.ts), api: s.api_ms, pending: s.pending }));
  const t = chartTheme(useIsDark());
  const apiColor = seriesColor(0);
  const pendingColor = seriesColor(1);

  return (
    <Card>
      <CardHeader
        title="پاسخگویی و تأخیر سرویس"
        action={
          <Segmented
            value={minutes}
            onChange={onMinutesChange}
            options={RANGES}
            size="sm"
            ariaLabel="بازهٔ نمودار"
          />
        }
      />
      <ChartLegend
        items={[
          { label: "تأخیر API تلگرام (ms)", color: apiColor },
          { label: "آپدیت‌های معلق", color: pendingColor },
        ]}
      />
      <ChartFrame
        height="h-60"
        empty={points.length === 0}
        emptyLabel="هنوز داده‌ای ثبت نشده (نمونه‌ها هر دقیقه جمع می‌شوند)"
      >
        <ResponsiveContainer width="100%" height="100%">
          <ComposedChart data={points} margin={{ top: 8, right: 8, left: -16, bottom: 0 }}>
            <defs>
              <AreaGradient id="g-api" color={apiColor} />
            </defs>
            <CartesianGrid {...gridProps(t)} />
            <XAxis dataKey="t" minTickGap={32} {...axisProps(t)} />
            <YAxis yAxisId="api" width={36} {...axisProps(t)} />
            <YAxis
              yAxisId="pending"
              orientation="right"
              width={28}
              allowDecimals={false}
              {...axisProps(t)}
            />
            <Tooltip {...t.tooltip} />
            <Area
              yAxisId="api"
              type="monotone"
              dataKey="api"
              name="تأخیر (ms)"
              stroke={apiColor}
              strokeWidth={2}
              fill="url(#g-api)"
              connectNulls={false}
            />
            <Line
              yAxisId="pending"
              type="monotone"
              dataKey="pending"
              name="معلق"
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
