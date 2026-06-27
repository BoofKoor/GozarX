import { Activity, Ban, CheckCircle2, Gift, Users, Zap } from "lucide-react";

import { ClaimsChart } from "@/components/dashboard/ClaimsChart";
import { StatCard } from "@/components/dashboard/StatCard";
import { Card } from "@/components/ui/Card";
import { Spinner } from "@/components/ui/Spinner";
import { useDashboard } from "@/hooks/useDashboard";
import { formatNumber } from "@/lib/format";

export function Dashboard() {
  const { data, isLoading, isError } = useDashboard();

  if (isLoading) {
    return (
      <div className="flex justify-center py-20">
        <Spinner className="h-8 w-8 text-brand" />
      </div>
    );
  }
  if (isError || !data) {
    return <Card>خطا در دریافت آمار. لطفاً بعداً تلاش کنید.</Card>;
  }

  return (
    <div className="space-y-6">
      <h1 className="text-xl font-bold">داشبورد</h1>
      <div className="grid grid-cols-2 gap-4 lg:grid-cols-3">
        <StatCard label="کل کاربران" value={formatNumber(data.total_users)} icon={Users} />
        <StatCard label="آزاد" value={formatNumber(data.available)} icon={Activity} />
        <StatCard label="کانفیگ فعال" value={formatNumber(data.active)} icon={CheckCircle2} />
        <StatCard label="مسدود" value={formatNumber(data.banned)} icon={Ban} />
        <StatCard label="کانفیگ امروز" value={formatNumber(data.configs_today)} icon={Zap} />
        <StatCard label="کل دعوت‌ها" value={formatNumber(data.referrals)} icon={Gift} />
      </div>
      <ClaimsChart data={data.claims_series} />
    </div>
  );
}
