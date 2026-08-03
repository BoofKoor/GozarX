import {
  Activity,
  CheckCircle2,
  Database,
  Download,
  Gift,
  Globe2,
  HeartPulse,
  LineChart,
  Percent,
  Radio,
  Repeat,
  UserPlus,
  Users,
  Zap,
} from "lucide-react";
import { useState } from "react";
import { toast } from "sonner";

import { ActivationPanel } from "@/components/dashboard/ActivationPanel";
import { ActiveUsersPanel } from "@/components/dashboard/ActiveUsersPanel";
import { ActivityChart } from "@/components/dashboard/ActivityChart";
import { ActivityHeatmap } from "@/components/dashboard/ActivityHeatmap";
import { ClaimsDistribution } from "@/components/dashboard/ClaimsDistribution";
import { ConversionPanel } from "@/components/dashboard/ConversionPanel";
import { CumulativeUsersChart } from "@/components/dashboard/CumulativeUsersChart";
import { EngagementPanel } from "@/components/dashboard/EngagementPanel";
import { LanguageDonut } from "@/components/dashboard/LanguageDonut";
import { NewVsReturningChart } from "@/components/dashboard/NewVsReturningChart";
import { ReferralFunnelPanel } from "@/components/dashboard/ReferralFunnelPanel";
import { ReminderByLanguage } from "@/components/dashboard/ReminderByLanguage";
import { RetentionCohorts } from "@/components/dashboard/RetentionCohorts";
import { StatCard } from "@/components/dashboard/StatCard";
import { TopLocations } from "@/components/dashboard/TopLocations";
import { TopReferrers } from "@/components/dashboard/TopReferrers";
import { TrialHealthPanel } from "@/components/dashboard/TrialHealthPanel";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Card, CardHeader } from "@/components/ui/Card";
import { EmptyState } from "@/components/ui/EmptyState";
import { ErrorState } from "@/components/ui/ErrorState";
import { PageHeader } from "@/components/ui/PageHeader";
import { Segmented } from "@/components/ui/Segmented";
import { Skeleton } from "@/components/ui/Skeleton";
import { Tabs } from "@/components/ui/Tabs";
import {
  RANGES,
  downloadDashboardCsv,
  useDashboard,
  useDashboardAnalytics,
  useRetention,
} from "@/hooks/useDashboard";
import { faPct, formatNumber, humanBytes } from "@/lib/format";
import type { DashboardAnalytics } from "@/types/api";

type TabKey = "overview" | "growth" | "retention" | "referrals" | "geo" | "health";

const TABS: { value: TabKey; label: string; icon: typeof LineChart }[] = [
  { value: "overview", label: "نمای کلی", icon: LineChart },
  { value: "growth", label: "رشد", icon: UserPlus },
  { value: "retention", label: "نگه‌داشت", icon: Repeat },
  { value: "referrals", label: "دعوت‌ها", icon: Gift },
  { value: "geo", label: "جغرافیا و رفتار", icon: Globe2 },
  { value: "health", label: "سلامت سرویس", icon: HeartPulse },
];

const RANGE_OPTIONS = RANGES.map((r) => ({ value: r as number, label: `${formatNumber(r)} روز` }));

/** Render an analytics panel once its (separate) query has loaded, else a stable skeleton so the
 *  grid doesn't jump when the deeper stats arrive a moment after the headline. */
function Analytic({
  data,
  render,
  height = "h-52",
}: {
  data: DashboardAnalytics | undefined;
  render: (d: DashboardAnalytics) => JSX.Element;
  height?: string;
}) {
  if (!data) {
    return (
      <Card>
        <Skeleton className={`${height} w-full`} />
      </Card>
    );
  }
  return render(data);
}

export function Dashboard() {
  const [days, setDays] = useState<number>(14);
  const [tab, setTab] = useState<TabKey>("overview");
  const [exporting, setExporting] = useState(false);
  const { data, isLoading, isError, refetch } = useDashboard(days);
  // Every windowed panel reads from these two queries, so the range control drives the WHOLE page —
  // it used to move only the activity chart while the panels beside it stayed on their own window.
  const { data: analytics } = useDashboardAnalytics(days);
  // Cohorts are inherently weekly, so they keep their own axis rather than the day range.
  const { data: retention } = useRetention(8);

  async function exportCsv() {
    setExporting(true);
    try {
      await downloadDashboardCsv(days);
    } catch {
      toast.error("خروجی گرفتن ممکن نشد.");
    } finally {
      setExporting(false);
    }
  }

  if (isLoading) {
    return <DashboardSkeleton />;
  }
  if (isError || !data) {
    return (
      <div className="space-y-6">
        <PageHeader title="داشبورد" />
        <ErrorState onRetry={() => refetch()} />
      </div>
    );
  }

  const signupsSpark = data.signups_series.map((p) => p.count);
  const claimsSpark = data.claims_series.map((p) => p.count);

  return (
    <div className="space-y-6">
      <PageHeader
        title="داشبورد"
        sub={`${formatNumber(data.range_days)} روز اخیر، در مقایسه با ${formatNumber(data.range_days)} روز پیش از آن`}
        actions={
          <>
            <Segmented
              value={days}
              onChange={setDays}
              options={RANGE_OPTIONS}
              size="sm"
              ariaLabel="بازهٔ زمانی"
            />
            <Button variant="outline" size="sm" onClick={exportCsv} loading={exporting}>
              <Download className="h-4 w-4" />
              <span className="hidden sm:inline">خروجی CSV</span>
            </Button>
          </>
        }
      >
        <Tabs value={tab} onChange={setTab} items={TABS} />
      </PageHeader>

      {tab === "overview" && (
        <>
          <div className="grid grid-cols-2 gap-4 md:grid-cols-3 xl:grid-cols-4">
            <StatCard
              label="آنلاین"
              value={formatNumber(data.online_now)}
              icon={Radio}
              tone="success"
              pulse={data.panel_online}
              hint={
                !data.panel_online
                  ? "تخمین از دیتابیس"
                  : data.online_squad_scoped
                    ? "آنلاینِ اسکواد سرویس"
                    : "هم‌اکنون متصل (کل پنل)"
              }
            />
            <StatCard
              label="کاربران جدید (بازه)"
              value={formatNumber(data.signups_in_range)}
              icon={UserPlus}
              tone="info"
              delta={data.signups_delta_pct}
              spark={signupsSpark}
              hint={`${formatNumber(data.signups_prev_range)} در بازهٔ قبل`}
            />
            <StatCard
              label="کل کاربران"
              value={formatNumber(data.total_users)}
              icon={Users}
              tone="brand"
              hint={`امروز ${formatNumber(data.new_today)} نفر`}
            />
            <StatCard
              label="کاربران فعال (بازه)"
              value={formatNumber(data.claimers_in_range)}
              icon={Activity}
              tone="brand"
              delta={data.claimers_delta_pct}
              hint={`${formatNumber(data.claimers_prev_range)} در بازهٔ قبل`}
            />
            <StatCard
              label="کانفیگ داده‌شده (بازه)"
              value={formatNumber(data.claims_in_range)}
              icon={Zap}
              tone="warning"
              delta={data.claims_delta_pct}
              spark={claimsSpark}
              hint={`امروز ${formatNumber(data.configs_today)}`}
            />
            <StatCard
              label="کانفیگ فعال"
              value={formatNumber(data.active)}
              icon={CheckCircle2}
              tone="info"
            />
            <StatCard
              label="نرخ تبدیل"
              value={faPct(data.conversion_pct)}
              icon={Percent}
              tone="brand"
              hint="کاربرانی که کانفیگ گرفته‌اند"
            />
            <StatCard
              label="ترافیک مصرفی"
              value={humanBytes(data.total_traffic_bytes)}
              icon={Database}
              tone="neutral"
              hint="کل عمر سرویس (از پنل)"
            />
          </div>

          <ActivityChart
            claims={data.claims_series}
            signups={data.signups_series}
            days={data.range_days}
          />
          <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
            <Analytic data={analytics} render={(d) => <ActiveUsersPanel data={d} />} />
            <EngagementPanel data={data} />
          </div>
        </>
      )}

      {tab === "growth" && (
        <>
          <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
            <CumulativeUsersChart signups={data.signups_series} total={data.total_users} />
            <Analytic
              data={analytics}
              render={(d) => <NewVsReturningChart data={d.new_vs_returning} />}
            />
          </div>
          <Analytic data={analytics} height="h-56" render={(d) => <ActiveUsersSeries data={d} />} />
          <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
            <Analytic data={analytics} render={(d) => <ActivationPanel data={d} />} />
            <ConversionPanel data={data} />
          </div>
        </>
      )}

      {tab === "retention" && (
        <>
          {retention ? (
            <RetentionCohorts data={retention} />
          ) : (
            <Card>
              <Skeleton className="h-64 w-full" />
            </Card>
          )}
          <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
            <Analytic data={analytics} render={(d) => <ActiveUsersPanel data={d} />} />
            <Analytic
              data={analytics}
              render={(d) => <ClaimsDistribution data={d.claims_distribution} />}
            />
          </div>
        </>
      )}

      {tab === "referrals" && (
        <>
          <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
            <Analytic data={analytics} render={(d) => <ReferralFunnelPanel data={d} />} />
            <Analytic data={analytics} render={(d) => <ReferralCapPanel data={d} />} />
          </div>
          <TopReferrers data={data.top_referrers} />
        </>
      )}

      {tab === "geo" && (
        <>
          <Analytic
            data={analytics}
            height="h-64"
            render={(d) => <ActivityHeatmap cells={d.heatmap} />}
          />
          <Analytic
            data={analytics}
            height="h-64"
            render={(d) => (
              <ActivityHeatmap
                cells={d.signup_heatmap}
                title="نقشهٔ حرارتی ثبت‌نام‌ها (به وقت تهران)"
                unit="ثبت‌نام"
                axisNote="ورود کاربران تازه بر حسب روز × ساعت"
              />
            )}
          />
          <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
            <TopLocations data={data.top_locations} />
            <LanguageDonut data={data.languages} />
          </div>
          <Analytic
            data={analytics}
            render={(d) => <ReminderByLanguage data={d.reminder_by_language} />}
          />
        </>
      )}

      {tab === "health" && (
        <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
          <TrialHealthPanel data={data} />
          <ConversionPanel data={data} />
        </div>
      )}
    </div>
  );
}

/** DAU as a trend rather than a single number — the dashboard only ever showed today's value. */
function ActiveUsersSeries({ data }: { data: DashboardAnalytics }) {
  const total = data.active_users_series.reduce((s, p) => s + p.count, 0);
  const peak = Math.max(1, ...data.active_users_series.map((p) => p.count));
  return (
    <Card>
      <CardHeader
        title="کاربران فعال روزانه"
        sub="تعداد افراد یکتایی که هر روز کانفیگ گرفته‌اند."
        icon={Activity}
        action={<Badge tone="brand">اوج {formatNumber(peak)}</Badge>}
      />
      {total === 0 ? (
        <EmptyState title="در این بازه کسی کانفیگ نگرفته است" />
      ) : (
        <div className="flex h-40 items-end gap-1" dir="ltr">
          {data.active_users_series.map((p) => (
            <div
              key={p.day}
              title={`${p.day}: ${formatNumber(p.count)}`}
              className="flex-1 rounded-t bg-brand/70 transition-colors hover:bg-brand"
              style={{ height: `${(p.count / peak) * 100}%`, minHeight: 2 }}
            />
          ))}
        </div>
      )}
    </Card>
  );
}

/** How many inviters have hit the configured reward ceiling and stopped earning. */
function ReferralCapPanel({ data }: { data: DashboardAnalytics }) {
  const { limit, at_cap, with_referrals } = data.referral_cap;
  const share = with_referrals ? (at_cap / with_referrals) * 100 : 0;
  return (
    <Card>
      <CardHeader
        title="سقف پاداش دعوت"
        sub={
          limit > 0
            ? `سقف فعلی: ${formatNumber(limit)} دعوت پاداش‌دار`
            : "سقفی تنظیم نشده — دعوت‌ها بی‌نهایت پاداش می‌گیرند."
        }
        icon={Gift}
        action={<Badge tone={share > 50 ? "warning" : "neutral"}>{faPct(share)}</Badge>}
      />
      {with_referrals === 0 ? (
        <EmptyState title="هنوز دعوت موفقی ثبت نشده" />
      ) : (
        <div className="space-y-3">
          <div className="grid grid-cols-2 gap-3">
            <div className="rounded-xl bg-surface-sunken p-3 text-center">
              <div className="text-xl font-bold tabular-nums text-content">
                {formatNumber(with_referrals)}
              </div>
              <div className="mt-0.5 text-xs text-content-muted">دعوت‌کنندهٔ فعال</div>
            </div>
            <div className="rounded-xl bg-surface-sunken p-3 text-center">
              <div className="text-xl font-bold tabular-nums text-content">
                {formatNumber(at_cap)}
              </div>
              <div className="mt-0.5 text-xs text-content-muted">رسیده به سقف</div>
            </div>
          </div>
          <div className="h-2 overflow-hidden rounded-full bg-surface-sunken">
            <div className="h-full rounded-full bg-brand" style={{ width: `${share}%` }} />
          </div>
          <p className="text-xs text-content-muted">
            کسانی که به سقف رسیده‌اند دیگر با دعوت تازه حجم نمی‌گیرند؛ اگر این نسبت بالا رفت، سقف را
            از «تنظیمات ربات» بالا ببرید.
          </p>
        </div>
      )}
    </Card>
  );
}

function DashboardSkeleton() {
  return (
    <div className="space-y-6">
      <PageHeader title="داشبورد" />
      <div className="grid grid-cols-2 gap-4 md:grid-cols-3 xl:grid-cols-4">
        {Array.from({ length: 8 }).map((_, i) => (
          <Card key={i} className="flex items-center gap-4">
            <Skeleton className="h-12 w-12 rounded-2xl" />
            <div className="flex-1 space-y-2">
              <Skeleton className="h-5 w-16" />
              <Skeleton className="h-3 w-20" />
            </div>
          </Card>
        ))}
      </div>
      <Card>
        <Skeleton className="mb-4 h-5 w-32" />
        <Skeleton className="h-64 w-full" />
      </Card>
      <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
        <Card>
          <Skeleton className="h-56 w-full" />
        </Card>
        <Card>
          <Skeleton className="h-56 w-full" />
        </Card>
      </div>
    </div>
  );
}
