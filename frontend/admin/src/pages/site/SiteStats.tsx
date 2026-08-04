import { Activity, BellRing, Download, Globe, MapPin, Repeat, UserPlus, Zap } from "lucide-react";
import { useState } from "react";
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
import { StatCard } from "@/components/dashboard/StatCard";
import { SiteAnalyticsSection } from "@/components/site/SiteAnalytics";
import { SiteTabs } from "@/components/site/SiteTabs";
import { Card, CardHeader } from "@/components/ui/Card";
import { ErrorState } from "@/components/ui/ErrorState";
import { PageHeader } from "@/components/ui/PageHeader";
import { Section } from "@/components/ui/Section";
import { Segmented } from "@/components/ui/Segmented";
import { Skeleton } from "@/components/ui/Skeleton";
import { Spinner } from "@/components/ui/Spinner";
import { useIsDark } from "@/hooks/useIsDark";
import { useSiteAnalytics, useSiteStats } from "@/hooks/useSite";
import { useI18n, type MessageKey } from "@/i18n";
import { chartTheme, seriesColor } from "@/lib/chartTheme";
import { faPct, formatNumber, shortDay } from "@/lib/format";
import type { DayPoint, SiteStats as SiteStatsData } from "@/types/api";

const RANGES = [7, 14, 30, 90];

const STATUS_LABEL: Record<string, MessageKey> = {
  available: "st.device.available",
  active_config: "st.device.active_config",
  blocked: "st.device.blocked",
};

/** Union the visitors and claims series onto one x-axis so the funnel gap is visible per day. */
function mergeSeries(visitors: DayPoint[], claims: DayPoint[]) {
  const by = new Map<string, { day: string; visitors: number; claims: number }>();
  for (const p of visitors) by.set(p.day, { day: p.day, visitors: p.count, claims: 0 });
  for (const p of claims) {
    const e = by.get(p.day) ?? { day: p.day, visitors: 0, claims: 0 };
    e.claims = p.count;
    by.set(p.day, e);
  }
  return [...by.values()]
    .sort((a, b) => a.day.localeCompare(b.day))
    .map((p) => ({ ...p, label: shortDay(p.day) }));
}

/**
 * The website funnel.
 *
 * Every KPI in the top band is WINDOWED and carries the previous, equal-length window as a delta —
 * the range control used to sit above numbers that were all-time or today-only, so changing it
 * moved nothing. The lifetime figures still have their place, but in their own clearly-labelled
 * card rather than posing as "visits this period".
 */
export function SiteStats() {
  const { t } = useI18n();
  const RANGE_OPTIONS = RANGES.map((r) => ({
    value: r,
    label: t("st.range.days", { n: formatNumber(r) }),
  }));
  const [days, setDays] = useState(14);
  const { data, isError, refetch } = useSiteStats(days);
  // Same window as the funnel above — the range control moves the WHOLE page.
  const { data: analytics } = useSiteAnalytics(days);

  return (
    <div className="space-y-6">
      <PageHeader
        title={t("st.title")}
        sub={t("st.sub")}
        actions={
          <Segmented
            value={days}
            onChange={setDays}
            options={RANGE_OPTIONS}
            size="sm"
            ariaLabel={t("st.rangeAria")}
          />
        }
      >
        <SiteTabs />
      </PageHeader>

      {!data ? (
        isError ? (
          <ErrorState onRetry={() => refetch()} />
        ) : (
          <div className="flex justify-center py-20">
            <Spinner className="h-8 w-8 text-brand" />
          </div>
        )
      ) : (
        <>
          <FunnelKpis data={data} days={days} />
          <ActivityCard data={data} days={days} />

          <div className="grid gap-6 lg:grid-cols-3">
            <TopLocationsCard data={data} days={days} />
            <LifetimeCard data={data} />
            <StatusCard data={data} />
          </div>

          {analytics ? (
            <SiteAnalyticsSection data={analytics} />
          ) : (
            <>
              <Section title={t("st.deep")} />
              <div className="grid gap-6 lg:grid-cols-2">
                <Card>
                  <Skeleton className="h-40 w-full" />
                </Card>
                <Card>
                  <Skeleton className="h-40 w-full" />
                </Card>
              </div>
            </>
          )}
        </>
      )}
    </div>
  );
}

function FunnelKpis({ data, days }: { data: SiteStatsData; days: number }) {
  const { t } = useI18n();
  const rangeLabel = t("st.rangeLabel", { n: formatNumber(days) });
  return (
    <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
      <StatCard
        label={t("st.kpi.visitors", { range: rangeLabel })}
        value={formatNumber(data.visitors.value)}
        icon={Globe}
        tone="brand"
        delta={data.visitors.change_pct}
        hint={t("st.prev", { n: formatNumber(data.visitors.previous) })}
        spark={data.visitors_series.map((p) => p.count)}
      />
      <StatCard
        label={t("st.kpi.newVisitors", { range: rangeLabel })}
        value={formatNumber(data.new_visitors.value)}
        icon={UserPlus}
        tone="info"
        delta={data.new_visitors.change_pct}
        hint={t("st.prev", { n: formatNumber(data.new_visitors.previous) })}
      />
      <StatCard
        label={t("st.kpi.returning", { range: rangeLabel })}
        value={formatNumber(data.returning_visitors.value)}
        icon={Repeat}
        tone="neutral"
        delta={data.returning_visitors.change_pct}
        hint={t("st.kpi.returningHint")}
      />
      <StatCard
        label={t("st.kpi.claimers", { range: rangeLabel })}
        value={formatNumber(data.claimers.value)}
        icon={Download}
        tone="success"
        delta={data.claimers.change_pct}
        hint={t("st.kpi.conversionHint", {
          now: faPct(data.conversion_pct),
          prev: faPct(data.conversion_pct_prev),
        })}
        spark={data.claims_series.map((p) => p.count)}
      />
      <StatCard
        label={t("st.kpi.activeNow")}
        value={formatNumber(data.active_configs_live)}
        icon={Zap}
        tone={data.active_configs_stale > 0 ? "warning" : "info"}
        // The status column alone overstates this: it is healed by the panel webhook or the
        // 15-minute sweep, and the sweep skips a device when the panel is unreachable. Naming the
        // stale rows turns an invisible overcount into a visible reconcile lag.
        hint={
          data.active_configs_stale > 0
            ? t("st.kpi.stale", { n: formatNumber(data.active_configs_stale) })
            : t("st.kpi.allSynced")
        }
      />
      <StatCard
        label={t("st.kpi.today")}
        value={formatNumber(data.configs_today)}
        icon={Activity}
        tone="brand"
        hint={t("st.kpi.todayHint")}
      />
    </div>
  );
}

function ActivityCard({ data, days }: { data: SiteStatsData; days: number }) {
  const { t } = useI18n();
  const points = mergeSeries(data.visitors_series, data.claims_series);
  const theme = chartTheme(useIsDark());
  const visitorsColor = seriesColor(1);
  const claimsColor = seriesColor(0);
  const empty = points.every((p) => p.visitors === 0 && p.claims === 0);

  return (
    <Card>
      <CardHeader title={t("st.daily")} sub={t("st.rangeLabel", { n: formatNumber(days) })} />
      <ChartLegend
        items={[
          { label: t("st.daily.visitors"), color: visitorsColor },
          { label: t("st.daily.claims"), color: claimsColor },
        ]}
      />
      <ChartFrame empty={empty}>
        <ResponsiveContainer width="100%" height="100%">
          <AreaChart data={points} margin={{ top: 8, right: 8, left: -16, bottom: 0 }}>
            <defs>
              <AreaGradient id="g-site-visitors" color={visitorsColor} />
              <AreaGradient id="g-site-claims" color={claimsColor} />
            </defs>
            <CartesianGrid {...gridProps(theme)} />
            <XAxis dataKey="label" {...axisProps(theme)} />
            <YAxis allowDecimals={false} width={32} {...axisProps(theme)} />
            <Tooltip {...theme.tooltip} />
            <Area
              type="monotone"
              dataKey="visitors"
              name={t("st.daily.visitors")}
              stroke={visitorsColor}
              strokeWidth={2}
              fill="url(#g-site-visitors)"
            />
            <Area
              type="monotone"
              dataKey="claims"
              name={t("st.daily.claims")}
              stroke={claimsColor}
              strokeWidth={2}
              fill="url(#g-site-claims)"
            />
          </AreaChart>
        </ResponsiveContainer>
      </ChartFrame>
    </Card>
  );
}

function TopLocationsCard({ data, days }: { data: SiteStatsData; days: number }) {
  const { t } = useI18n();
  const max = Math.max(1, ...data.top_locations.map((l) => l.count));
  const hidden = data.locations_total - data.top_locations.length;

  return (
    <Card>
      <CardHeader
        title={t("st.top")}
        icon={MapPin}
        // The list is capped at 10; saying so is the difference between "these are the locations"
        // and "these are the busiest ten of N".
        sub={
          hidden > 0
            ? t("st.top.hidden", { n: formatNumber(days), hidden: formatNumber(hidden) })
            : t("st.rangeLabel", { n: formatNumber(days) })
        }
      />
      {data.top_locations.length === 0 ? (
        <p className="py-4 text-center text-sm text-content-subtle">{t("st.noData")}</p>
      ) : (
        <ul className="space-y-2">
          {data.top_locations.map((l) => (
            <li key={l.label}>
              <div className="mb-1 flex justify-between text-sm">
                <span dir="auto" className="truncate">
                  {l.label}
                </span>
                <span className="tabular-nums text-content-muted">{formatNumber(l.count)}</span>
              </div>
              <div className="h-2 overflow-hidden rounded-full bg-surface-sunken">
                <div
                  className="h-full rounded-full bg-brand transition-all"
                  style={{ width: `${(l.count / max) * 100}%` }}
                />
              </div>
            </li>
          ))}
        </ul>
      )}
    </Card>
  );
}

function LifetimeCard({ data }: { data: SiteStatsData }) {
  const { t } = useI18n();
  return (
    <Card>
      <CardHeader title={t("st.allTime")} sub={t("st.allTime.sub")} icon={Globe} />
      <ul className="space-y-2 text-sm">
        <Row label={t("st.allTime.identities")} value={formatNumber(data.total_devices_all_time)} />
        <Row label={t("st.allTime.claimers")} value={formatNumber(data.devices_claimed_all_time)} />
        <Row label={t("st.allTime.conversion")} value={faPct(data.conversion_all_time_pct)} />
        <Row label={t("st.allTime.subscribers")} value={formatNumber(data.push_subscribers)} />
        <Row label={t("st.allTime.relocations")} value={formatNumber(data.location_changes)} />
      </ul>
      <p className="mt-3 text-xs leading-relaxed text-content-subtle">{t("st.allTime.note")}</p>
    </Card>
  );
}

function StatusCard({ data }: { data: SiteStatsData }) {
  const { t } = useI18n();
  const entries = Object.entries(data.status_counts);
  return (
    <Card>
      <CardHeader title={t("st.deviceStatus")} icon={BellRing} />
      <ul className="space-y-2 text-sm">
        {entries.map(([status, count]) => (
          <Row
            key={status}
            label={STATUS_LABEL[status] ? t(STATUS_LABEL[status]) : status}
            value={formatNumber(count)}
          />
        ))}
        {entries.length === 0 && (
          <li className="py-4 text-center text-content-subtle">{t("st.noData")}</li>
        )}
      </ul>
    </Card>
  );
}

function Row({ label, value }: { label: string; value: string }) {
  return (
    <li className="flex items-center justify-between gap-2 border-b border-line py-2 last:border-0">
      <span className="text-content-muted">{label}</span>
      <span className="tabular-nums text-content">{value}</span>
    </li>
  );
}
