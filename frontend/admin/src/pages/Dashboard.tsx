import { Activity, Ban, CheckCircle2, Gift, Radio, Users, Zap } from "lucide-react";
import { useState } from "react";

import { ActivityChart } from "@/components/dashboard/ActivityChart";
import { LanguageDonut } from "@/components/dashboard/LanguageDonut";
import { StatCard } from "@/components/dashboard/StatCard";
import { TopLocations } from "@/components/dashboard/TopLocations";
import { TopReferrers } from "@/components/dashboard/TopReferrers";
import { Card } from "@/components/ui/Card";
import { Skeleton } from "@/components/ui/Skeleton";
import { useDashboard } from "@/hooks/useDashboard";
import { formatNumber } from "@/lib/format";

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
          pulse
          hint="کاربران فعال اسکواد"
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
          label="آزاد"
          value={formatNumber(data.available)}
          icon={Activity}
          tone="neutral"
        />
        <StatCard
          label="کانفیگ امروز"
          value={formatNumber(data.configs_today)}
          icon={Zap}
          tone="warning"
        />
        <StatCard
          label="کل دعوت‌ها"
          value={formatNumber(data.referrals)}
          icon={Gift}
          tone="brand"
        />
        <StatCard label="مسدود" value={formatNumber(data.banned)} icon={Ban} tone="danger" />
      </div>

      <ActivityChart
        claims={data.claims_series}
        signups={data.signups_series}
        days={data.range_days}
        onDaysChange={setDays}
      />

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
        <LanguageDonut data={data.languages} />
        <TopLocations data={data.top_locations} />
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
        {Array.from({ length: 7 }).map((_, i) => (
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
          <Skeleton className="h-40 w-full" />
        </Card>
        <Card>
          <Skeleton className="h-40 w-full" />
        </Card>
      </div>
    </div>
  );
}
