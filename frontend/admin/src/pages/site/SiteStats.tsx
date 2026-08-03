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
import { chartTheme, seriesColor } from "@/lib/chartTheme";
import { faPct, formatNumber, shortDay } from "@/lib/format";
import type { DayPoint, SiteStats as SiteStatsData } from "@/types/api";

const RANGE_OPTIONS = [7, 14, 30, 90].map((r) => ({ value: r, label: `${formatNumber(r)} روز` }));

const STATUS_LABEL: Record<string, string> = {
  available: "آزاد",
  active_config: "دارای کانفیگ",
  blocked: "مسدود",
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
  const [days, setDays] = useState(14);
  const { data, isError, refetch } = useSiteStats(days);
  // Same window as the funnel above — the range control moves the WHOLE page.
  const { data: analytics } = useSiteAnalytics(days);

  return (
    <div className="space-y-6">
      <PageHeader
        title="آمار وب‌سایت"
        sub="قیف بازدید تا دریافت کانفیگ، و تحلیل عمیق‌تر رفتار بازدیدکننده‌ها."
        actions={
          <Segmented
            value={days}
            onChange={setDays}
            options={RANGE_OPTIONS}
            size="sm"
            ariaLabel="بازهٔ زمانی"
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
              <Section title="تحلیل عمیق وب‌سایت" />
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
  const rangeLabel = `${formatNumber(days)} روز اخیر`;
  return (
    <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
      <StatCard
        label={`بازدیدکننده (${rangeLabel})`}
        value={formatNumber(data.visitors.value)}
        icon={Globe}
        tone="brand"
        delta={data.visitors.change_pct}
        hint={`دورهٔ قبل: ${formatNumber(data.visitors.previous)}`}
        spark={data.visitors_series.map((p) => p.count)}
      />
      <StatCard
        label={`بازدیدکنندهٔ تازه (${rangeLabel})`}
        value={formatNumber(data.new_visitors.value)}
        icon={UserPlus}
        tone="info"
        delta={data.new_visitors.change_pct}
        hint={`دورهٔ قبل: ${formatNumber(data.new_visitors.previous)}`}
      />
      <StatCard
        label={`بازگشتی (${rangeLabel})`}
        value={formatNumber(data.returning_visitors.value)}
        icon={Repeat}
        tone="neutral"
        delta={data.returning_visitors.change_pct}
        hint="پیش از این بازه ساخته شده، در این بازه دیده شده"
      />
      <StatCard
        label={`دریافت‌کننده (${rangeLabel})`}
        value={formatNumber(data.claimers.value)}
        icon={Download}
        tone="success"
        delta={data.claimers.change_pct}
        hint={`نرخ تبدیل: ${faPct(data.conversion_pct)} (قبل: ${faPct(data.conversion_pct_prev)})`}
        spark={data.claims_series.map((p) => p.count)}
      />
      <StatCard
        label="کانفیگ فعال (اکنون)"
        value={formatNumber(data.active_configs_live)}
        icon={Zap}
        tone={data.active_configs_stale > 0 ? "warning" : "info"}
        // The status column alone overstates this: it is healed by the panel webhook or the
        // 15-minute sweep, and the sweep skips a device when the panel is unreachable. Naming the
        // stale rows turns an invisible overcount into a visible reconcile lag.
        hint={
          data.active_configs_stale > 0
            ? `${formatNumber(data.active_configs_stale)} مورد منقضی ولی هنوز هم‌گام‌نشده`
            : "همه هم‌گام"
        }
      />
      <StatCard
        label="دریافت امروز"
        value={formatNumber(data.configs_today)}
        icon={Activity}
        tone="brand"
        hint="بر اساس روز تقویمی تهران"
      />
    </div>
  );
}

function ActivityCard({ data, days }: { data: SiteStatsData; days: number }) {
  const points = mergeSeries(data.visitors_series, data.claims_series);
  const t = chartTheme(useIsDark());
  const visitorsColor = seriesColor(1);
  const claimsColor = seriesColor(0);
  const empty = points.every((p) => p.visitors === 0 && p.claims === 0);

  return (
    <Card>
      <CardHeader title="بازدید و دریافت روزانه" sub={`${formatNumber(days)} روز اخیر`} />
      <ChartLegend
        items={[
          { label: "بازدیدکننده", color: visitorsColor },
          { label: "دریافت کانفیگ", color: claimsColor },
        ]}
      />
      <ChartFrame empty={empty}>
        <ResponsiveContainer width="100%" height="100%">
          <AreaChart data={points} margin={{ top: 8, right: 8, left: -16, bottom: 0 }}>
            <defs>
              <AreaGradient id="g-site-visitors" color={visitorsColor} />
              <AreaGradient id="g-site-claims" color={claimsColor} />
            </defs>
            <CartesianGrid {...gridProps(t)} />
            <XAxis dataKey="label" {...axisProps(t)} />
            <YAxis allowDecimals={false} width={32} {...axisProps(t)} />
            <Tooltip {...t.tooltip} />
            <Area
              type="monotone"
              dataKey="visitors"
              name="بازدیدکننده"
              stroke={visitorsColor}
              strokeWidth={2}
              fill="url(#g-site-visitors)"
            />
            <Area
              type="monotone"
              dataKey="claims"
              name="دریافت کانفیگ"
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
  const max = Math.max(1, ...data.top_locations.map((l) => l.count));
  const hidden = data.locations_total - data.top_locations.length;

  return (
    <Card>
      <CardHeader
        title="پرطرفدارترین لوکیشن‌ها"
        icon={MapPin}
        // The list is capped at 10; saying so is the difference between "these are the locations"
        // and "these are the busiest ten of N".
        sub={
          hidden > 0
            ? `${formatNumber(days)} روز اخیر · ${formatNumber(hidden)} لوکیشن دیگر نمایش داده نشده`
            : `${formatNumber(days)} روز اخیر`
        }
      />
      {data.top_locations.length === 0 ? (
        <p className="py-4 text-center text-sm text-content-subtle">داده‌ای نیست.</p>
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
  return (
    <Card>
      <CardHeader title="از ابتدا تاکنون" sub="مستقل از بازهٔ انتخابی" icon={Globe} />
      <ul className="space-y-2 text-sm">
        <Row label="شناسهٔ ساخته‌شده" value={formatNumber(data.total_devices_all_time)} />
        <Row label="دریافت‌کننده" value={formatNumber(data.devices_claimed_all_time)} />
        <Row label="نرخ تبدیل کل" value={faPct(data.conversion_all_time_pct)} />
        <Row label="مشترک اعلان" value={formatNumber(data.push_subscribers)} />
        <Row label="تعویض لوکیشن (این بازه)" value={formatNumber(data.location_changes)} />
      </ul>
      <p className="mt-3 text-xs leading-relaxed text-content-subtle">
        «شناسهٔ ساخته‌شده» تعداد بازدید نیست: مرورگری که کوکی نگه نمی‌دارد در هر درخواست یک شناسهٔ
        تازه می‌سازد. عدد بازدید بالای صفحه از آخرین حضور واقعی دستگاه‌ها به دست می‌آید.
      </p>
    </Card>
  );
}

function StatusCard({ data }: { data: SiteStatsData }) {
  const entries = Object.entries(data.status_counts);
  return (
    <Card>
      <CardHeader title="وضعیت دستگاه‌ها" icon={BellRing} />
      <ul className="space-y-2 text-sm">
        {entries.map(([status, count]) => (
          <Row key={status} label={STATUS_LABEL[status] ?? status} value={formatNumber(count)} />
        ))}
        {entries.length === 0 && (
          <li className="py-4 text-center text-content-subtle">داده‌ای نیست.</li>
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
