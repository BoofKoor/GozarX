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

import { ActivityChart } from "@/components/dashboard/ActivityChart";
import { ConversionPanel } from "@/components/dashboard/ConversionPanel";
import { CumulativeUsersChart } from "@/components/dashboard/CumulativeUsersChart";
import { EngagementPanel } from "@/components/dashboard/EngagementPanel";
import { LanguageDonut } from "@/components/dashboard/LanguageDonut";
import { StatCard } from "@/components/dashboard/StatCard";
import { TopLocations } from "@/components/dashboard/TopLocations";
import { TopReferrers } from "@/components/dashboard/TopReferrers";
import { TrialHealthPanel } from "@/components/dashboard/TrialHealthPanel";
import { Card } from "@/components/ui/Card";
import { Skeleton } from "@/components/ui/Skeleton";
import { useDashboard } from "@/hooks/useDashboard";
import { formatNumber, humanBytes } from "@/lib/format";

export function Dashboard() {
  const [days, setDays] = useState(14);
  const { data, isLoading, isError } = useDashboard(days);

  if (isLoading) {
    return <DashboardSkeleton />;
  }
  if (isError || !data) {
    return <Card>خطا در دریافت آمار. لطفاً بعداً تلاش کنید.</Card>;
  }

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
          hint={data.panel_online ? "هم‌اکنون متصل" : "تخمین از دیتابیس"}
        />
        <StatCard
          label="کاربران جدید امروز"
          value={formatNumber(data.new_today)}
          icon={UserPlus}
          tone="info"
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
        />
        <StatCard
          label="نرخ تبدیل"
          value={`${data.conversion_pct}%`}
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

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
        <TrialHealthPanel data={data} />
        <LanguageDonut data={data.languages} />
      </div>

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
        <TopLocations data={data.top_locations} />
        <ConversionPanel data={data} />
      </div>

      <TopReferrers data={data.top_referrers} />
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
