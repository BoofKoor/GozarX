import { AlertTriangle, Gauge, HardDrive, Users, Wifi } from "lucide-react";
import {
  Area,
  AreaChart,
  Bar,
  BarChart,
  CartesianGrid,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import { AreaGradient, ChartFrame, axisProps, gridProps } from "@/components/charts/primitives";
import { Badge } from "@/components/ui/Badge";
import { Card, CardHeader } from "@/components/ui/Card";
import { EmptyState } from "@/components/ui/EmptyState";
import { useIsDark } from "@/hooks/useIsDark";
import { useSeriesAnimation } from "@/hooks/useReducedMotion";
import { useI18n } from "@/i18n";
import { CHART_MARGIN, Y_AXIS_WIDTH, chartTheme, seriesColor, tokenColor } from "@/lib/chartTheme";
import { faDate, faPct, formatNumber, humanBytes, shortDay } from "@/lib/format";
import type { DashboardUsage, Metric } from "@/types/api";

/** A windowed figure with its previous-window delta. The tab's range control moves all four. */
function UsageStat({
  icon: Icon,
  label,
  value,
  metric,
  hint,
}: {
  icon: typeof Gauge;
  label: string;
  value: string;
  metric?: Metric;
  hint?: string;
}) {
  const { t } = useI18n();
  const change = metric?.change_pct ?? null;
  return (
    // Same reading order as the overview tab's KPI band: the FIGURE first, its label as an eyebrow
    // underneath, the delta at the floor. Built the other way round — label and icon on top, number
    // in the middle — the two tabs taught opposite hierarchies one click apart, and the eye had to
    // relearn where the answer was.
    <Card className="flex flex-col">
      <div className="text-[1.6rem] font-bold leading-tight tracking-[-0.02em] tabular-nums text-content">
        {value}
      </div>
      <div className="mt-1.5 flex items-center gap-1.5 text-content-subtle">
        <Icon className="h-3.5 w-3.5 shrink-0" />
        <span className="text-[10px] uppercase leading-[1.5] tracking-[0.085em]">{label}</span>
      </div>
      <div className="mt-auto pt-2.5 text-xs">
        {change === null ? (
          // A null baseline is "nothing to compare against", not "flat". Rendering it as 0% would
          // claim a steady period where there was no previous period at all.
          <span className="text-content-subtle">{hint ?? t("d.usage.noBaseline")}</span>
        ) : (
          <span
            className={change >= 0 ? "font-medium text-success-700" : "font-medium text-danger-700"}
          >
            {/* Its own inline run: a signed percentage beside Persian text reorders without one. */}
            <span dir="ltr">
              {change >= 0 ? "▲" : "▼"} {faPct(Math.abs(change))}
            </span>
          </span>
        )}
      </div>
    </Card>
  );
}

/**
 * Traffic and concurrency over time.
 *
 * Everything here comes from the hourly `usage_samples` recorder, because the panel itself reports
 * only a cumulative lifetime counter and a live concurrency reading — neither of which can answer
 * "what did last Tuesday look like". The series therefore starts when the recorder shipped, and
 * this component is careful to SAY that rather than draw a flat line through the time before it
 * existed.
 */
export function UsagePanel({ data }: { data: DashboardUsage }) {
  const { t } = useI18n();
  const theme = chartTheme(useIsDark());
  const anim = useSeriesAnimation();
  const trafficColor = seriesColor(0);
  const onlineColor = seriesColor(2);
  const resetColor = tokenColor("warning-500");
  // Room for a formatted byte tick with its unit, unlike the plain-count default.
  const BYTE_AXIS_WIDTH = 74;

  const points = data.daily.map((d) => ({ ...d, label: shortDay(d.day) }));
  const resets = data.daily.filter((d) => d.counter_reset).length;
  const memPct = data.mem_total > 0 ? (data.mem_used / data.mem_total) * 100 : null;

  // Gate on whether there is a chartable DAY, not on the raw sample count. A day's traffic is the
  // difference between two days' readings, so a second sample an hour after the first adds nothing
  // to plot — and gating on `samples >= 2` would replace this one clear sentence with a KPI band
  // above two charts saying only "no data", which is the explanation disappearing exactly when it
  // is still needed. It also matches what the copy promises: two samples on two different days.
  if (!data.recording_since || points.length === 0) {
    // Recording for two days with still nothing to plot is not warming up — it is samples not
    // landing, and telling the operator to wait 48 hours would send them away from a real problem.
    const hoursRecording = data.recording_since
      ? (Date.now() - Date.parse(data.recording_since)) / 3_600_000
      : 0;
    const stale = Boolean(data.recording_since) && hoursRecording >= 48;
    return (
      <Card>
        <CardHeader title={t("d.usage")} sub={t("d.usage.sub")} icon={Gauge} />
        <EmptyState
          icon={Gauge}
          title={stale ? t("d.usage.gap") : t("d.usage.warmup")}
          message={
            !data.recording_since
              ? t("d.usage.warmup.notYet")
              : stale
                ? t("d.usage.gap.hint", { date: faDate(data.recording_since) })
                : t("d.usage.warmup.since", { date: faDate(data.recording_since) })
          }
        />
      </Card>
    );
  }

  return (
    <div className="flex flex-col gap-4">
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <UsageStat
          icon={Gauge}
          label={t("d.usage.traffic")}
          value={humanBytes(data.traffic.value)}
          metric={data.traffic}
        />
        <UsageStat
          icon={Wifi}
          label={t("d.usage.peak")}
          value={formatNumber(data.peak_online.value)}
          metric={data.peak_online}
        />
        <UsageStat
          icon={Users}
          label={t("d.usage.perUser")}
          value={humanBytes(data.bytes_per_user.value)}
          metric={data.bytes_per_user}
        />
        <UsageStat
          icon={HardDrive}
          label={t("d.usage.nodes")}
          value={formatNumber(data.nodes_online)}
          // Nodes online is a LIVE reading, not a window — it has no previous-period twin, and the
          // hint says what it does have rather than showing a delta that would be invented.
          hint={
            memPct === null
              ? t("d.usage.nodes.hint")
              : t("d.usage.mem", { pct: faPct(memPct), total: humanBytes(data.mem_total) })
          }
        />
      </div>

      <Card>
        <CardHeader
          title={t("d.usage.trafficDaily")}
          sub={t("d.usage.trafficDaily.sub")}
          icon={Gauge}
          action={
            resets > 0 ? (
              <Badge tone="warning">
                <AlertTriangle className="h-3 w-3" />
                {t("d.usage.resets", { n: formatNumber(resets) })}
              </Badge>
            ) : undefined
          }
        />
        <ChartFrame height="h-56" empty={points.length === 0}>
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={points} margin={CHART_MARGIN}>
              <CartesianGrid {...gridProps(theme)} />
              <XAxis dataKey="label" {...axisProps(theme)} />
              {/* A byte tick carries a unit ("۱۳۰٫۴ GB"), so the 46px sized for three Persian
                  digits wraps it onto two lines. Widened here rather than globally: no other chart
                  formats its ticks this way. */}
              <YAxis
                width={BYTE_AXIS_WIDTH}
                {...axisProps(theme)}
                tickFormatter={(v: number) => humanBytes(v)}
              />
              <Tooltip {...theme.tooltip} formatter={(v: number) => humanBytes(v)} />
              {/* A reset day reads 0, so a tinted BAR would be a zero-height bar — invisible,
                  which is exactly the gap that needs explaining. A reference line marks the day
                  without claiming a quantity for it: the point is "not measurable here", not
                  "a little traffic here". */}
              {points
                .filter((p) => p.counter_reset)
                .map((p) => (
                  <ReferenceLine
                    key={p.day}
                    x={p.label}
                    stroke={resetColor}
                    strokeDasharray="3 3"
                    strokeWidth={2}
                  />
                ))}
              <Bar
                {...anim}
                dataKey="bytes"
                name={t("d.usage.traffic")}
                fill={trafficColor}
                radius={[3, 3, 0, 0]}
              />
            </BarChart>
          </ResponsiveContainer>
        </ChartFrame>
        {resets > 0 && (
          <p className="mt-3 text-xs text-content-subtle">{t("d.usage.resets.note")}</p>
        )}
      </Card>

      <Card>
        <CardHeader
          title={t("d.usage.online")}
          sub={t("d.usage.online.sub")}
          icon={Wifi}
          action={
            <Badge tone="brand">
              {t("d.usage.peakAt", { n: formatNumber(data.peak_online.value) })}
            </Badge>
          }
        />
        <ChartFrame height="h-56" empty={points.length === 0}>
          <ResponsiveContainer width="100%" height="100%">
            <AreaChart data={points} margin={CHART_MARGIN}>
              <defs>
                <AreaGradient id="g-online" color={onlineColor} />
              </defs>
              <CartesianGrid {...gridProps(theme)} />
              <XAxis dataKey="label" {...axisProps(theme)} />
              <YAxis allowDecimals={false} width={Y_AXIS_WIDTH} {...axisProps(theme)} />
              <Tooltip {...theme.tooltip} />
              <Area
                {...anim}
                type="monotone"
                dataKey="peak_online"
                name={t("d.usage.peak")}
                stroke={onlineColor}
                strokeWidth={2}
                fill="url(#g-online)"
              />
            </AreaChart>
          </ResponsiveContainer>
        </ChartFrame>
        <p className="mt-3 text-xs text-content-subtle">
          {t("d.usage.since", { date: faDate(data.recording_since) })}
        </p>
      </Card>
    </div>
  );
}
