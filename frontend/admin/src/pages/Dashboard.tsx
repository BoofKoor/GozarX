import {
  Activity,
  CheckCircle2,
  Database,
  Percent,
  Radio,
  UserPlus,
  Users,
  Zap,
} from "lucide-react";
import { useState } from "react";

import { ActivationPanel } from "@/components/dashboard/ActivationPanel";
import { ActiveUsersPanel } from "@/components/dashboard/ActiveUsersPanel";
import { ActivityChart } from "@/components/dashboard/ActivityChart";
import { ActivityHeatmap } from "@/components/dashboard/ActivityHeatmap";
import { ClaimsDistribution } from "@/components/dashboard/ClaimsDistribution";
import { ConversionPanel } from "@/components/dashboard/ConversionPanel";
import { CumulativeUsersChart } from "@/components/dashboard/CumulativeUsersChart";
import { EngagementPanel } from "@/components/dashboard/EngagementPanel";
import { LanguageDonut } from "@/components/dashboard/LanguageDonut";
import { ReferralFunnelPanel } from "@/components/dashboard/ReferralFunnelPanel";
import { ReminderByLanguage } from "@/components/dashboard/ReminderByLanguage";
import { StatCard } from "@/components/dashboard/StatCard";
import { TopLocations } from "@/components/dashboard/TopLocations";
import { TopReferrers } from "@/components/dashboard/TopReferrers";
import { TrialHealthPanel } from "@/components/dashboard/TrialHealthPanel";
import { Card } from "@/components/ui/Card";
import { ErrorState } from "@/components/ui/ErrorState";
import { Section } from "@/components/ui/Section";
import { Skeleton } from "@/components/ui/Skeleton";
import { useDashboard, useDashboardAnalytics } from "@/hooks/useDashboard";
import { formatNumber, humanBytes } from "@/lib/format";
import type { DashboardAnalytics } from "@/types/api";

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
  const [days, setDays] = useState(14);
  const { data, isLoading, isError, refetch } = useDashboard(days);
  const { data: analytics } = useDashboardAnalytics(days);

  if (isLoading) {
    return <DashboardSkeleton />;
  }
  if (isError || !data) {
    return (
      <div className="space-y-6">
        <h1 className="text-xl font-bold">داشبورد</h1>
        <ErrorState onRetry={() => refetch()} />
      </div>
    );
  }

  const signupsSpark = data.signups_series.map((p) => p.count);
  const claimsSpark = data.claims_series.map((p) => p.count);

  return (
    <div className="space-y-6">
      <h1 className="text-xl font-bold">داشبورد</h1>

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
          label="کاربران جدید امروز"
          value={formatNumber(data.new_today)}
          icon={UserPlus}
          tone="info"
          delta={data.growth_pct}
          spark={signupsSpark}
          hint={`${formatNumber(data.new_this_week)} در ۷ روز اخیر`}
        />
        <StatCard
          label="کل کاربران"
          value={formatNumber(data.total_users)}
          icon={Users}
          tone="brand"
        />
        <StatCard
          label="کانفیگ فعال"
          value={formatNumber(data.active)}
          icon={CheckCircle2}
          tone="info"
        />
        <StatCard
          label="کانفیگ امروز"
          value={formatNumber(data.configs_today)}
          icon={Zap}
          tone="warning"
          spark={claimsSpark}
        />
        <StatCard
          label="نرخ تبدیل"
          value={`${formatNumber(data.conversion_pct)}٪`}
          icon={Percent}
          tone="brand"
          hint="کاربرانی که کانفیگ گرفته‌اند"
        />
        <StatCard
          label="ترافیک مصرفی"
          value={humanBytes(data.total_traffic_bytes)}
          icon={Database}
          tone="neutral"
        />
        <StatCard
          label="آزاد"
          value={formatNumber(data.available)}
          icon={Activity}
          tone="neutral"
        />
      </div>

      <Section title="رشد و نگه‌داشت" />
      <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
        <Analytic data={analytics} render={(d) => <ActiveUsersPanel data={d} />} />
        <Analytic data={analytics} render={(d) => <ActivationPanel data={d} />} />
      </div>
      <ActivityChart
        claims={data.claims_series}
        signups={data.signups_series}
        days={data.range_days}
        onDaysChange={setDays}
      />
      <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
        <CumulativeUsersChart signups={data.signups_series} total={data.total_users} />
        <EngagementPanel data={data} />
      </div>

      <Section title="دعوت‌ها" />
      <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
        <Analytic data={analytics} render={(d) => <ReferralFunnelPanel data={d} />} />
        <TopReferrers data={data.top_referrers} />
      </div>

      <Section title="جغرافیا و رفتار" />
      <Analytic
        data={analytics}
        height="h-64"
        render={(d) => <ActivityHeatmap cells={d.heatmap} />}
      />
      <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
        <TopLocations data={data.top_locations} />
        <Analytic
          data={analytics}
          render={(d) => <ClaimsDistribution data={d.claims_distribution} />}
        />
      </div>
      <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
        <LanguageDonut data={data.languages} />
        <Analytic
          data={analytics}
          render={(d) => <ReminderByLanguage data={d.reminder_by_language} />}
        />
      </div>

      <Section title="سلامت سرویس" />
      <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
        <TrialHealthPanel data={data} />
        <ConversionPanel data={data} />
      </div>
    </div>
  );
}

function DashboardSkeleton() {
  return (
    <div className="space-y-6">
      <h1 className="text-xl font-bold">داشبورد</h1>
      <div className="grid grid-cols-2 gap-4 md:grid-cols-3 xl:grid-cols-4">
        {Array.from({ length: 8 }).map((_, i) => (
          <Card key={i} className="flex items-center gap-4">
            <Skeleton className="h-12 w-12 rounded-xl" />
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
